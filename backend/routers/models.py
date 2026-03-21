import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException
from config import MODELS_DIR

router = APIRouter()


@router.get("/")
async def list_models():
    models = []
    for f in sorted(MODELS_DIR.glob("*.pt")):
        models.append(
            {
                "name": f.name,
                "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
            }
        )
    return models


@router.post("/upload")
async def upload_model(file: UploadFile = File(...)):
    if not (file.filename or "").endswith(".pt"):
        raise HTTPException(status_code=400, detail="Only .pt model files are supported")
    dest = MODELS_DIR / file.filename
    with open(dest, "wb") as buf:
        shutil.copyfileobj(file.file, buf)
    return {"name": file.filename, "size_mb": round(dest.stat().st_size / (1024 * 1024), 2)}


@router.delete("/{model_name}")
async def delete_model(model_name: str):
    target = MODELS_DIR / model_name
    if not target.exists() or target.suffix != ".pt":
        raise HTTPException(status_code=404, detail="Model not found")
    target.unlink()
    return {"deleted": model_name}
