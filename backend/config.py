import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
MODELS_DIR = BASE_DIR / "models"
DOWNLOADS_DIR = BASE_DIR / "downloads"
HLS_DIR = BASE_DIR / "hls"
RESULTS_DIR = BASE_DIR / "results"

for d in [MODELS_DIR, DOWNLOADS_DIR, HLS_DIR, RESULTS_DIR]:
    d.mkdir(exist_ok=True)

TBA_API_KEY: str = os.getenv("TBA_API_KEY", "")
TBA_BASE_URL = "https://www.thebluealliance.com/api/v3"

# YOLO class IDs – must match how the model was trained
ROBOT_CLASS_ID = 0
BALL_CLASS_ID = 1

# After this many consecutive frames without a track, trigger re-identification
REIDENTIFY_THRESHOLD_FRAMES: int = int(os.getenv("REIDENTIFY_THRESHOLD_FRAMES", "30"))

HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8000"))
