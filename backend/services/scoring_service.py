"""
Scoring Service
===============
Processes each video frame to:
1. Detect ball ownership: a ball is "owned" by the last robot that shot it.
   Shot detection = ball bbox exits a robot's bbox from the upper 2/3 of that
   robot (i.e. ball center y < robot_y1 + robot_height * 2/3 at exit moment).
2. Detect Hub scoring: if an owned/in-flight ball overlaps a Hub zone whose
   alliance matches the owning robot's alliance, award a point.

State
-----
ball_states  dict[int, BallState]   keyed by YOLO ball track_id
scores       dict[int, int]         keyed by team_number

This service is designed to be easy to extend: add more scoring methods by
creating additional `process_*` methods and calling them from `process_frame`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BallState:
    ball_id: int
    owned_by: Optional[int] = None       # team_number of owning robot
    in_flight: bool = False              # was shot (exited upper 2/3)
    prev_inside_robot: Optional[int] = None  # track_id of robot it was inside
    prev_bbox: Optional[dict] = None

    # extensibility: store per-ball event history
    events: list = field(default_factory=list)


class ScoringService:

    def process_frame(
        self,
        frame_idx: int,
        current_robots: dict[int, dict],  # track_id → {team, bbox}
        current_balls: dict[int, dict],   # track_id → {bbox}
        ball_states: dict[int, BallState],
        hub_zones: list[dict],            # [{alliance, bbox}]
        team_alliance: dict[int, str],    # team_number → "red"|"blue"
        scores: dict[int, int],
    ) -> None:
        """
        Main entry point called once per video frame.
        Mutates ball_states and scores in-place.
        """
        self._process_ball_ownership(
            frame_idx, current_robots, current_balls, ball_states, team_alliance
        )
        self._process_hub_scoring(
            frame_idx, current_balls, ball_states, hub_zones, team_alliance, scores
        )
        # Future scoring methods can be plugged in here:
        # self._process_ground_scoring(...)

    # ── Ball ownership ────────────────────────────────────────────────────────

    def _process_ball_ownership(
        self,
        frame_idx: int,
        current_robots: dict[int, dict],
        current_balls: dict[int, dict],
        ball_states: dict[int, BallState],
        team_alliance: dict[int, str],
    ) -> None:
        for ball_id, ball_info in current_balls.items():
            if ball_id not in ball_states:
                ball_states[ball_id] = BallState(ball_id)
            state = ball_states[ball_id]

            ball_bbox = ball_info["bbox"]
            ball_cx = (ball_bbox["x1"] + ball_bbox["x2"]) / 2
            ball_cy = (ball_bbox["y1"] + ball_bbox["y2"]) / 2

            currently_inside: Optional[int] = None  # robot track_id
            for robot_tid, robot_info in current_robots.items():
                if _bbox_contains_point(robot_info["bbox"], ball_cx, ball_cy):
                    currently_inside = robot_tid
                    break

            if currently_inside is not None:
                state.prev_inside_robot = currently_inside
                state.in_flight = False

            elif state.prev_inside_robot is not None:
                # Ball just exited a robot – check if it was a shot
                robot_info = current_robots.get(state.prev_inside_robot)
                if robot_info:
                    rbox = robot_info["bbox"]
                    robot_height = rbox["y2"] - rbox["y1"]
                    upper_two_thirds_y = rbox["y1"] + robot_height * (2.0 / 3.0)

                    if ball_cy < upper_two_thirds_y:
                        # Shot detected — assign ownership
                        owning_team = robot_info["team"]
                        state.owned_by = owning_team
                        state.in_flight = True
                        state.events.append(
                            {"event": "shot", "frame": frame_idx, "team": owning_team}
                        )

                state.prev_inside_robot = None

            state.prev_bbox = ball_bbox

    # ── Hub scoring ───────────────────────────────────────────────────────────

    def _process_hub_scoring(
        self,
        frame_idx: int,
        current_balls: dict[int, dict],
        ball_states: dict[int, BallState],
        hub_zones: list[dict],
        team_alliance: dict[int, str],
        scores: dict[int, int],
    ) -> None:
        to_remove: list[int] = []

        for ball_id, ball_info in current_balls.items():
            state = ball_states.get(ball_id)
            if state is None or not (state.in_flight or state.owned_by is not None):
                continue

            ball_bbox = ball_info["bbox"]
            ball_cx = (ball_bbox["x1"] + ball_bbox["x2"]) / 2
            ball_cy = (ball_bbox["y1"] + ball_bbox["y2"]) / 2

            for hub in hub_zones:
                if not _bbox_contains_point(hub["bbox"], ball_cx, ball_cy):
                    continue

                owning_team = state.owned_by
                if owning_team is None:
                    continue

                team_color = team_alliance.get(owning_team, "")
                if team_color != hub["alliance"]:
                    # Wrong hub for this alliance – no point
                    continue

                # Award point
                scores[owning_team] = scores.get(owning_team, 0) + 1
                state.events.append(
                    {
                        "event": "scored",
                        "frame": frame_idx,
                        "team": owning_team,
                        "hub_alliance": hub["alliance"],
                    }
                )
                to_remove.append(ball_id)
                break  # ball consumed

        for ball_id in to_remove:
            ball_states.pop(ball_id, None)


# ── Geometry helpers ──────────────────────────────────────────────────────────

def _bbox_contains_point(bbox: dict, px: float, py: float) -> bool:
    return bbox["x1"] <= px <= bbox["x2"] and bbox["y1"] <= py <= bbox["y2"]
