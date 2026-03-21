from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from services.video_service import VideoService

router = APIRouter()
_video = VideoService()


class DownloadRequest(BaseModel):
    match_key: str
    youtube_key: str


@router.post("/download")
async def download_video(req: DownloadRequest, background_tasks: BackgroundTasks):
    job_id = _video.create_download_job(req.match_key)
    background_tasks.add_task(
        _video.download_and_convert, job_id, req.match_key, req.youtube_key
    )
    return {"job_id": job_id}


@router.get("/download-status/{job_id}")
async def download_status(job_id: str):
    status = _video.get_download_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    return status


@router.get("/hls/{match_key}")
async def get_hls_info(match_key: str):
    info = _video.get_hls_info(match_key)
    if not info:
        raise HTTPException(status_code=404, detail="HLS stream not ready")
    return info


@router.get("/info/{match_key}")
async def get_video_info(match_key: str):
    info = _video.get_video_info(match_key)
    if not info:
        raise HTTPException(status_code=404, detail="Video not found")
    return info


@router.get("/frame/{match_key}/{frame_number}")
async def get_frame(match_key: str, frame_number: int):
    return await _video.get_frame(match_key, frame_number)
