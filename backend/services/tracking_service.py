"""
Tracking Service
================
Runs YOLO26s + BoT-SORT tracking in a thread-pool worker, and exposes an
asyncio-compatible interface so FastAPI WebSocket handlers can stream progress
and bi-directionally handle re-identification pauses.

Thread-safety model
-------------------
- The heavy CV/YOLO work runs in a ThreadPoolExecutor.
- asyncio.Queue (event_queue)  : tracker thread → WebSocket clients.
- threading.Event (resume_event): WebSocket handler → tracker thread (unblock pause).
- The tracker calls `asyncio.run_coroutine_threadsafe` to push to the queue from
  the worker thread.
"""

from __future__ import annotations

import asyncio
import base64
import concurrent.futures
import threading
import uuid
from pathlib import Path
from typing import Any, Optional

import cv2

from config import DOWNLOADS_DIR, MODELS_DIR, ROBOT_CLASS_ID, BALL_CLASS_ID, REIDENTIFY_THRESHOLD_FRAMES
from services.scoring_service import ScoringService, BallState
from services.heatmap_service import HeatmapService

# Global registry of all tracking jobs
tracking_jobs: dict[str, dict] = {}

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
_scoring_svc = ScoringService()
_heatmap_svc = HeatmapService()


class TrackingService:

    # ── Job lifecycle ─────────────────────────────────────────────────────────

    def create_job(self, req: Any) -> str:
        job_id = str(uuid.uuid4())
        tracking_jobs[job_id] = {
            "job_id": job_id,
            "match_key": req.match_key,
            "robot_model": req.robot_model,
            "ball_model": req.ball_model,
            "first_frame": req.first_frame,
            "robots": [r.dict() for r in req.robots],
            "hub_zones": [h.dict() for h in req.hub_zones],
            "status": "pending",
            "progress": 0.0,
            "current_frame": req.first_frame,
            "total_frames": None,
            "error": None,
            "result_id": None,
            # asyncio primitives – set in run_tracking
            "event_queue": asyncio.Queue(),
            "resume_event": threading.Event(),
            "reidentify_response": None,
        }
        return job_id

    # ── Single-frame detection (for annotation step) ──────────────────────────

    async def detect_frame(self, match_key: str, robot_model: str, frame_number: int) -> dict:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor, self._detect_frame_sync, match_key, robot_model, frame_number
        )

    def _detect_frame_sync(self, match_key: str, robot_model: str, frame_number: int) -> dict:
        """Run only the robot model for first-frame annotation."""
        from ultralytics import YOLO

        video_path = DOWNLOADS_DIR / f"{match_key}.mp4"
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        cap = cv2.VideoCapture(str(video_path))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()
        cap.release()
        if not ret:
            raise ValueError(f"Cannot read frame {frame_number}")

        model = YOLO(str(MODELS_DIR / robot_model))
        results = model(frame, verbose=False)
        detections: list[dict] = []
        if results and results[0].boxes is not None:
            for box in results[0].boxes:
                cls = int(box.cls[0])
                if cls != ROBOT_CLASS_ID:
                    continue  # Only return robots for first-frame annotation
                conf = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                detections.append(
                    {
                        "class_id": cls,
                        "class_name": "robot",
                        "confidence": round(conf, 3),
                        "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                    }
                )

        _, buf = cv2.imencode(".jpg", frame)
        frame_b64 = base64.b64encode(buf).decode()

        return {
            "frame_number": frame_number,
            "frame_image": frame_b64,
            "detections": detections,
            "frame_width": frame.shape[1],
            "frame_height": frame.shape[0],
        }

    # ── Tracking pipeline ─────────────────────────────────────────────────────

    async def run_tracking(self, job_id: str) -> None:
        loop = asyncio.get_event_loop()
        job = tracking_jobs[job_id]
        job["status"] = "running"
        await loop.run_in_executor(_executor, self._tracking_thread, job_id, loop)

    def _tracking_thread(self, job_id: str, loop: asyncio.AbstractEventLoop) -> None:
        """Heavy CV work – runs in a thread-pool worker."""
        from ultralytics import YOLO
        import numpy as np

        job = tracking_jobs[job_id]

        def emit(msg: dict) -> None:
            """Thread-safe push to the async event queue."""
            asyncio.run_coroutine_threadsafe(job["event_queue"].put(msg), loop).result(timeout=5)

        try:
            video_path = DOWNLOADS_DIR / f"{job['match_key']}.mp4"
            # Robot model runs BoT-SORT tracking; ball model (optional) detects balls
            robot_model = YOLO(str(MODELS_DIR / job["robot_model"]))
            ball_model = (
                YOLO(str(MODELS_DIR / job["ball_model"]))
                if job["ball_model"]
                else None
            )

            cap = cv2.VideoCapture(str(video_path))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 30
            job["total_frames"] = total_frames

            cap.set(cv2.CAP_PROP_POS_FRAMES, job["first_frame"])

            # Build team→alliance lookup from annotations
            team_alliance: dict[int, str] = {
                r["team_number"]: r["alliance"] for r in job["robots"]
            }

            # BoT-SORT track_id → team_number (populated from first-frame annotations)
            track_to_team: dict[int, int] = {}

            # Frames each track_id has been absent
            frames_lost: dict[int, int] = {}

            # Tracks temporarily snoozed after user chooses "drop/skip" in
            # re-identification. Maps lost track_id -> frame index when
            # re-identification prompts may resume for that track.
            reidentify_snooze_until: dict[int, int] = {}

            # Per-team position history: team → [(cx, cy, frame_idx), ...]
            positions: dict[int, list[tuple[float, float, int]]] = {
                r["team_number"]: [] for r in job["robots"]
            }

            # Most recent known bbox per team. Seed from initial annotations so
            # re-identification prompts can show a "last seen" hint immediately.
            last_known_bbox_by_team: dict[int, dict] = {
                r["team_number"]: r["bbox"] for r in job["robots"]
            }

            # Scoring state
            scores: dict[int, int] = {r["team_number"]: 0 for r in job["robots"]}
            ball_states: dict[int, BallState] = {}  # ball_track_id → BallState

            hub_zones = [
                {"alliance": h["alliance"], "bbox": h["bbox"]}
                for h in job["hub_zones"]
            ]

            # Pending re-identification hints from user-drawn bboxes.
            # Maps team_number → {"bbox": ..., "ttl": frames_remaining}
            # Each frame we try to match these against unassigned BoT-SORT detections.
            pending_reident: dict[int, dict] = {}
            REIDENT_HINT_TTL = 60  # try for up to 60 frames

            # Initial annotation boxes should act as suggestions, not just a
            # single-frame hard match. Keep unmatched annotations as hints for
            # a short time so tracks that appear a few frames later can still
            # be assigned to the intended teams.
            pending_annotation_hints: dict[int, dict] = {
                r["team_number"]: {"bbox": r["bbox"], "ttl": 180}
                for r in job["robots"]
            }

            frame_idx = job["first_frame"]
            first_frame_matched = False

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Robot model runs tracking (BoT-SORT persists state)
                results = robot_model.track(
                    frame,
                    persist=True,
                    tracker="botsort.yaml",
                    verbose=False,
                )

                boxes = results[0].boxes if results and results[0].boxes is not None else None

                current_track_ids: set[int] = set()
                current_robots: dict[int, dict] = {}   # track_id → {team, bbox}
                current_balls: dict[int, dict] = {}    # track_id → {bbox}

                if boxes is not None:
                    for box in boxes:
                        if box.id is None:
                            continue
                        track_id = int(box.id[0])
                        cls = int(box.cls[0])
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        bbox = {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
                        current_track_ids.add(track_id)

                        if cls == ROBOT_CLASS_ID:
                            # First-frame: match detection to annotated robot by IoU
                            if not first_frame_matched and frame_idx == job["first_frame"]:
                                best_team = self._match_annotation_to_detection(
                                    bbox, job["robots"], track_to_team
                                )
                                if best_team is not None:
                                    track_to_team[track_id] = best_team
                                    frames_lost.pop(track_id, None)
                                    reidentify_snooze_until.pop(track_id, None)
                                    pending_annotation_hints.pop(best_team, None)

                            if track_id in track_to_team:
                                current_robots[track_id] = {
                                    "team": track_to_team[track_id],
                                    "bbox": bbox,
                                }
                                cx = (x1 + x2) / 2
                                cy = (y1 + y2) / 2
                                team = track_to_team[track_id]
                                positions[team].append((cx, cy, frame_idx))

                # ── Match pending bbox hints against unassigned detections ────
                # Re-identification hints are explicit user input from a pause,
                # so we use a stricter IoU threshold than startup suggestions.
                self._assign_pending_bbox_hints(
                    boxes=boxes,
                    track_to_team=track_to_team,
                    pending_hints=pending_reident,
                    current_robots=current_robots,
                    positions=positions,
                    frame_idx=frame_idx,
                    frames_lost=frames_lost,
                    min_iou=0.2,
                )

                # Initial annotation hints are weaker suggestions.
                self._assign_pending_bbox_hints(
                    boxes=boxes,
                    track_to_team=track_to_team,
                    pending_hints=pending_annotation_hints,
                    current_robots=current_robots,
                    positions=positions,
                    frame_idx=frame_idx,
                    frames_lost=frames_lost,
                    min_iou=0.1,
                )

                # Refresh each team's last known location from assigned robots
                # visible on this frame.
                for info in current_robots.values():
                    last_known_bbox_by_team[info["team"]] = info["bbox"]

                # Ball model (or fallback to robot model) detects balls
                if ball_model:
                    ball_results = ball_model(frame, verbose=False)
                else:
                    # If no dedicated ball model, pull balls from the robot model's results
                    ball_results = results

                ball_boxes = ball_results[0].boxes if ball_results and ball_results[0].boxes is not None else None
                if ball_boxes is not None:
                    _next_ball_id = max(current_track_ids, default=9000) + 1
                    for bbox_item in ball_boxes:
                        bcls = int(bbox_item.cls[0])
                        if bcls != BALL_CLASS_ID:
                            continue
                        bx1, by1, bx2, by2 = bbox_item.xyxy[0].tolist()
                        bbbox = {"x1": bx1, "y1": by1, "x2": bx2, "y2": by2}
                        # De-dup against already-known balls
                        duplicate = any(
                            _iou(bbbox, b["bbox"]) > 0.5
                            for b in current_balls.values()
                        )
                        if not duplicate:
                            current_balls[_next_ball_id] = {"bbox": bbbox}
                            _next_ball_id += 1

                if frame_idx == job["first_frame"]:
                    first_frame_matched = True

                # ── Detect lost tracks ────────────────────────────────────────
                known_tracks = set(track_to_team.keys())
                for tid in list(known_tracks):
                    if tid not in current_track_ids:
                        frames_lost[tid] = frames_lost.get(tid, 0) + 1
                        snooze_until = reidentify_snooze_until.get(tid)
                        if snooze_until is not None and frame_idx < snooze_until:
                            continue
                        if frames_lost[tid] >= REIDENTIFY_THRESHOLD_FRAMES:
                            # Pause and ask user – pass track_to_team by ref so it can be mutated
                            self._trigger_reidentify(
                                job_id, job, loop, emit, frame, frame_idx,
                                tid, track_to_team[tid], team_alliance,
                                current_robots, track_to_team,
                                pending_reident, REIDENT_HINT_TTL,
                                reidentify_snooze_until,
                                last_known_bbox_by_team,
                            )
                            frames_lost.pop(tid, None)
                    else:
                        frames_lost[tid] = 0  # reset on re-detect
                        reidentify_snooze_until.pop(tid, None)

                # ── Scoring logic ─────────────────────────────────────────────
                _scoring_svc.process_frame(
                    frame_idx,
                    current_robots,
                    current_balls,
                    ball_states,
                    hub_zones,
                    team_alliance,
                    scores,
                )

                # ── Progress update (every 30 frames) ─────────────────────────
                if (frame_idx - job["first_frame"]) % 30 == 0:
                    span = max(1, total_frames - job["first_frame"])
                    pct = (frame_idx - job["first_frame"]) / span
                    job["progress"] = round(pct * 100, 1)
                    job["current_frame"] = frame_idx
                    emit({
                        "type": "progress",
                        "progress": job["progress"],
                        "frame": frame_idx,
                        "total_frames": total_frames,
                    })

                frame_idx += 1

            # Capture frame dimensions before releasing the capture object
            frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)
            frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
            cap.release()

            # ── Generate outputs ───────────────────────────────────────────────
            frame_shape = (frame_height, frame_width)

            model_label = job["robot_model"]
            if job["ball_model"]:
                model_label += f" + {job['ball_model']}"
            result_id = _heatmap_svc.save_results(
                job_id=job_id,
                match_key=job["match_key"],
                model_name=model_label,
                scores=scores,
                positions=positions,
                team_alliance=team_alliance,
                hub_zones=hub_zones,
                frame_shape=frame_shape,
            )

            job["status"] = "completed"
            job["progress"] = 100.0
            job["result_id"] = result_id
            emit({"type": "completed", "job_id": job_id, "result_id": result_id})

        except Exception as exc:
            job["status"] = "failed"
            job["error"] = str(exc)
            emit({"type": "error", "job_id": job_id, "message": str(exc)})

    # ── Re-identification ─────────────────────────────────────────────────────

    def _trigger_reidentify(
        self,
        job_id: str,
        job: dict,
        loop: asyncio.AbstractEventLoop,
        emit,
        frame,
        frame_idx: int,
        lost_tid: int,
        lost_team: int,
        team_alliance: dict[int, str],
        current_robots: dict[int, dict],
        track_to_team: dict[int, int],
        pending_reident: dict[int, dict],
        reident_hint_ttl: int,
        reidentify_snooze_until: dict[int, int],
        last_known_bbox_by_team: dict[int, dict],
    ) -> None:
        """Pause the tracker thread, send a reidentify event, and wait for the client."""
        _, buf = cv2.imencode(".jpg", frame)
        frame_b64 = base64.b64encode(buf).decode()

        active = [
            {
                "track_id": tid,
                "team_number": info["team"],
                "alliance": team_alliance.get(info["team"], "unknown"),
                "bbox": info["bbox"],
            }
            for tid, info in current_robots.items()
        ]

        job["status"] = "paused_reidentify"
        job["resume_event"].clear()
        job["reidentify_response"] = None

        emit({
            "type": "reidentify_needed",
            "job_id": job_id,
            "lost_team": lost_team,
            "lost_alliance": team_alliance.get(lost_team, "unknown"),
            "frame_number": frame_idx,
            "frame_image": frame_b64,
            "frame_width": frame.shape[1],
            "frame_height": frame.shape[0],
            "last_known_bbox": last_known_bbox_by_team.get(lost_team),
            "active_tracks": active,
        })

        # Block thread until user responds (5-minute timeout)
        responded = job["resume_event"].wait(timeout=300)
        reidentify_snooze_until.pop(lost_tid, None)

        if responded and job["reidentify_response"]:
            resp = job["reidentify_response"]
            new_tid = resp.get("new_track_id")
            drawn_bbox = resp.get("drawn_bbox")

            if drawn_bbox:
                # User drew a bounding box for the lost robot.
                # Store as a pending hint — we'll match it against real
                # BoT-SORT detections on upcoming frames.
                track_to_team.pop(lost_tid, None)
                pending_reident[lost_team] = {
                    "bbox": drawn_bbox,
                    "ttl": reident_hint_ttl,
                }
            elif new_tid is not None and new_tid != lost_tid:
                # Remove old (now-lost) track, map the newly selected track to the team
                track_to_team.pop(lost_tid, None)
                track_to_team[new_tid] = lost_team
            elif new_tid is None:
                # User chose to temporarily skip this robot. Keep the mapping,
                # but snooze re-identification prompts for one lost-threshold
                # window instead of dropping the robot forever.
                reidentify_snooze_until[lost_tid] = frame_idx + REIDENTIFY_THRESHOLD_FRAMES

        job["status"] = "running"

    # ── WebSocket handler ─────────────────────────────────────────────────────

    async def handle_websocket(self, job_id: str, websocket) -> None:
        from fastapi import WebSocketDisconnect

        job = tracking_jobs.get(job_id)
        if not job:
            await websocket.close(code=4004)
            return

        queue: asyncio.Queue = job["event_queue"]

        async def send_loop():
            while True:
                msg = await queue.get()
                try:
                    await websocket.send_json(msg)
                except Exception:
                    break
                if msg.get("type") in ("completed", "error"):
                    break

        async def recv_loop():
            try:
                while True:
                    data = await websocket.receive_json()
                    if data.get("type") == "reidentify_response":
                        job["reidentify_response"] = data
                        job["resume_event"].set()
            except WebSocketDisconnect:
                pass

        await asyncio.gather(send_loop(), recv_loop())

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _match_annotation_to_detection(
        detection_bbox: dict, robots: list[dict], already_assigned: dict[int, int]
    ) -> int | None:
        """Return the team number whose annotation bbox best overlaps this detection."""
        assigned_teams = set(already_assigned.values())
        best_iou = 0.0
        best_team = None
        for robot in robots:
            if robot["team_number"] in assigned_teams:
                continue
            iou = _iou(detection_bbox, robot["bbox"])
            if iou > best_iou:
                best_iou = iou
                best_team = robot["team_number"]
        return best_team if best_iou > 0.1 else None

    @staticmethod
    def _assign_pending_bbox_hints(
        boxes,
        track_to_team: dict[int, int],
        pending_hints: dict[int, dict],
        current_robots: dict[int, dict],
        positions: dict[int, list[tuple[float, float, int]]],
        frame_idx: int,
        frames_lost: dict[int, int],
        min_iou: float,
    ) -> None:
        """Assign unclaimed robot detections to teams using pending bbox hints."""
        if not pending_hints or boxes is None:
            return

        assigned_tids = set(track_to_team.keys())
        assigned_teams = set(track_to_team.values())

        for box in boxes:
            if box.id is None:
                continue
            tid = int(box.id[0])
            if tid in assigned_tids:
                continue

            bcls = int(box.cls[0])
            if bcls != ROBOT_CLASS_ID:
                continue

            bx1, by1, bx2, by2 = box.xyxy[0].tolist()
            det_bbox = {"x1": bx1, "y1": by1, "x2": bx2, "y2": by2}

            best_team = None
            best_iou = min_iou
            for team_num, hint in list(pending_hints.items()):
                if team_num in assigned_teams:
                    continue
                iou = _iou(det_bbox, hint["bbox"])
                if iou > best_iou:
                    best_iou = iou
                    best_team = team_num

            if best_team is None:
                continue

            track_to_team[tid] = best_team
            frames_lost.pop(tid, None)
            current_robots[tid] = {"team": best_team, "bbox": det_bbox}
            cx = (bx1 + bx2) / 2
            cy = (by1 + by2) / 2
            positions[best_team].append((cx, cy, frame_idx))

            assigned_tids.add(tid)
            assigned_teams.add(best_team)
            del pending_hints[best_team]

        # Tick down TTL and expire stale hints
        for team_num in list(pending_hints.keys()):
            pending_hints[team_num]["ttl"] -= 1
            if pending_hints[team_num]["ttl"] <= 0:
                del pending_hints[team_num]


# ── Geometry helpers ──────────────────────────────────────────────────────────

def _iou(a: dict, b: dict) -> float:
    ix1 = max(a["x1"], b["x1"])
    iy1 = max(a["y1"], b["y1"])
    ix2 = min(a["x2"], b["x2"])
    iy2 = min(a["y2"], b["y2"])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter == 0:
        return 0.0
    area_a = (a["x2"] - a["x1"]) * (a["y2"] - a["y1"])
    area_b = (b["x2"] - b["x1"]) * (b["y2"] - b["y1"])
    return inter / (area_a + area_b - inter)


def _nms_merge(detections: list[dict], iou_threshold: float = 0.5) -> list[dict]:
    """Class-aware greedy NMS: keep the highest-confidence box when two overlap."""
    from collections import defaultdict

    by_class: dict[int, list[dict]] = defaultdict(list)
    for d in detections:
        by_class[d["class_id"]].append(d)

    merged: list[dict] = []
    for _cls, dets in by_class.items():
        dets.sort(key=lambda d: d["confidence"], reverse=True)
        keep: list[dict] = []
        while dets:
            best = dets.pop(0)
            keep.append(best)
            dets = [
                d for d in dets
                if _iou(best["bbox"], d["bbox"]) < iou_threshold
            ]
        merged.extend(keep)
    return merged
