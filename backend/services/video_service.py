import asyncio
import tempfile
import uuid
from pathlib import Path
from typing import Optional

import cv2
from fastapi import HTTPException
from fastapi.responses import FileResponse

from config import DOWNLOADS_DIR, HLS_DIR

# In-process job registry; replace with a persistent store for production
download_jobs: dict[str, dict] = {}


class VideoService:
    # ── Job management ────────────────────────────────────────────────────────

    def create_download_job(self, match_key: str) -> str:
        job_id = str(uuid.uuid4())
        download_jobs[job_id] = {
            "job_id": job_id,
            "match_key": match_key,
            "status": "pending",
            "progress": 0,
            "error": None,
        }
        return job_id

    def get_download_status(self, job_id: str) -> Optional[dict]:
        return download_jobs.get(job_id)

    # ── Download + convert ────────────────────────────────────────────────────

    async def download_and_convert(self, job_id: str, match_key: str, youtube_key: str) -> None:
        job = download_jobs[job_id]
        try:
            job["status"] = "downloading"
            output_path = DOWNLOADS_DIR / f"{match_key}.mp4"
            url = f"https://www.youtube.com/watch?v={youtube_key}"

            proc = await asyncio.create_subprocess_exec(
                "yt-dlp",
                "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "--merge-output-format", "mp4",
                "-o", str(output_path),
                url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                job["status"] = "failed"
                job["error"] = stderr.decode(errors="replace")
                return

            job["status"] = "converting"
            job["progress"] = 50

            hls_dir = HLS_DIR / match_key
            hls_dir.mkdir(exist_ok=True)
            manifest = hls_dir / "playlist.m3u8"

            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y",
                "-i", str(output_path),
                "-codec:", "copy",
                "-start_number", "0",
                "-hls_time", "10",
                "-hls_list_size", "0",
                "-hls_segment_filename", str(hls_dir / "segment%04d.ts"),
                "-f", "hls",
                str(manifest),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                job["status"] = "failed"
                job["error"] = stderr.decode(errors="replace")
                return

            job["status"] = "completed"
            job["progress"] = 100

        except Exception as exc:
            job["status"] = "failed"
            job["error"] = str(exc)

    # ── HLS info ──────────────────────────────────────────────────────────────

    def get_hls_info(self, match_key: str) -> Optional[dict]:
        manifest = HLS_DIR / match_key / "playlist.m3u8"
        if not manifest.exists():
            return None
        return {"hls_url": f"/hls/{match_key}/playlist.m3u8", "match_key": match_key}

    # ── Video metadata ────────────────────────────────────────────────────────

    def get_video_info(self, match_key: str) -> Optional[dict]:
        path = DOWNLOADS_DIR / f"{match_key}.mp4"
        if not path.exists():
            return None
        cap = cv2.VideoCapture(str(path))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        return {
            "fps": fps,
            "total_frames": total,
            "width": width,
            "height": height,
            "duration": total / fps if fps > 0 else 0,
        }

    # ── Frame extraction ──────────────────────────────────────────────────────

    async def get_frame(self, match_key: str, frame_number: int) -> FileResponse:
        path = DOWNLOADS_DIR / f"{match_key}.mp4"
        if not path.exists():
            raise HTTPException(status_code=404, detail="Video not found")

        cap = cv2.VideoCapture(str(path))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            raise HTTPException(status_code=400, detail="Cannot read frame at that index")

        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        cv2.imwrite(tmp.name, frame)
        tmp.close()
        return FileResponse(tmp.name, media_type="image/jpeg")
