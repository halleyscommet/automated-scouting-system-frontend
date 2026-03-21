from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

from config import HOST, PORT, HLS_DIR, RESULTS_DIR
from routers import tba, video, models, tracking, results

app = FastAPI(title="Seer AI – FRC Tracking", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve HLS segments and result artifacts (heatmap images, etc.) as static files
app.mount("/hls", StaticFiles(directory=str(HLS_DIR)), name="hls")
app.mount("/results-static", StaticFiles(directory=str(RESULTS_DIR)), name="results-static")

app.include_router(tba.router, prefix="/api/tba", tags=["TBA"])
app.include_router(video.router, prefix="/api/video", tags=["Video"])
app.include_router(models.router, prefix="/api/models", tags=["Models"])
app.include_router(tracking.router, prefix="/api/tracking", tags=["Tracking"])
app.include_router(results.router, prefix="/api/results", tags=["Results"])


if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
