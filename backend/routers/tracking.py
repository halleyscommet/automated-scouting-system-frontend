from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
from services.tracking_service import TrackingService, tracking_jobs

router = APIRouter()
_tracking = TrackingService()


# ── Request models ────────────────────────────────────────────────────────────

class BBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class RobotAnnotation(BaseModel):
    team_number: int
    alliance: str   # "red" | "blue"
    bbox: BBox


class HubZone(BaseModel):
    alliance: str   # "red" | "blue"
    bbox: BBox


class DetectFrameRequest(BaseModel):
    match_key: str
    robot_model: str
    frame_number: int


class StartTrackingRequest(BaseModel):
    match_key: str
    robot_model: str
    ball_model: Optional[str] = None
    first_frame: int
    robots: List[RobotAnnotation]
    hub_zones: List[HubZone]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/detect-frame")
async def detect_frame(req: DetectFrameRequest):
    """Run YOLO inference with the robot model only (first-frame annotation)."""
    try:
        return await _tracking.detect_frame(req.match_key, req.robot_model, req.frame_number)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start")
async def start_tracking(req: StartTrackingRequest, background_tasks: BackgroundTasks):
    job_id = _tracking.create_job(req)
    background_tasks.add_task(_tracking.run_tracking, job_id)
    return {"job_id": job_id}


@router.get("/status/{job_id}")
async def tracking_status(job_id: str):
    job = tracking_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job_id,
        "status": job["status"],
        "progress": job["progress"],
        "current_frame": job.get("current_frame"),
        "total_frames": job.get("total_frames"),
        "error": job.get("error"),
        "result_id": job.get("result_id"),
    }


@router.websocket("/ws/{job_id}")
async def tracking_ws(websocket: WebSocket, job_id: str):
    await websocket.accept()
    await _tracking.handle_websocket(job_id, websocket)
