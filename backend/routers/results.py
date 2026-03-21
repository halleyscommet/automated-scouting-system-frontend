import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from config import RESULTS_DIR

router = APIRouter()


@router.get("/")
async def list_results():
    results = []
    for d in sorted(RESULTS_DIR.iterdir(), reverse=True):
        manifest = d / "results.json"
        if d.is_dir() and manifest.exists():
            with open(manifest) as f:
                data = json.load(f)
            results.append(
                {
                    "result_id": d.name,
                    "match_key": data.get("match_key"),
                    "timestamp": data.get("timestamp"),
                    "scoring": data.get("scoring"),
                }
            )
    return results


@router.get("/{result_id}")
async def get_result(result_id: str):
    manifest = RESULTS_DIR / result_id / "results.json"
    if not manifest.exists():
        raise HTTPException(status_code=404, detail="Result not found")
    with open(manifest) as f:
        return json.load(f)


@router.get("/{result_id}/heatmap/{team_number}")
async def get_heatmap(result_id: str, team_number: int):
    path = RESULTS_DIR / result_id / f"heatmap_{team_number}.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Heatmap not found")
    return FileResponse(str(path), media_type="image/png")


@router.delete("/{result_id}")
async def delete_result(result_id: str):
    import shutil
    target = RESULTS_DIR / result_id
    if not target.exists():
        raise HTTPException(status_code=404, detail="Result not found")
    shutil.rmtree(target)
    return {"deleted": result_id}
