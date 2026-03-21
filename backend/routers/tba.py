from fastapi import APIRouter, HTTPException
from services.tba_service import TBAService

router = APIRouter()
_tba = TBAService()


@router.get("/events/{year}")
async def get_events(year: int):
    try:
        return await _tba.get_events(year)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/event/{event_key}/matches")
async def get_matches_with_videos(event_key: str):
    try:
        return await _tba.get_event_matches_with_videos(event_key)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/match/{match_key}/teams")
async def get_match_teams(match_key: str):
    try:
        return await _tba.get_match_teams(match_key)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/match/{match_key}/youtube")
async def get_match_youtube(match_key: str):
    try:
        key = await _tba.get_match_youtube_key(match_key)
        if not key:
            raise HTTPException(status_code=404, detail="No YouTube video for this match")
        return {"youtube_key": key}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
