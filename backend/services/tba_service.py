import httpx
from config import TBA_API_KEY, TBA_BASE_URL


class TBAService:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=TBA_BASE_URL,
            headers={"X-TBA-Auth-Key": TBA_API_KEY},
            timeout=15,
        )

    async def get_events(self, year: int) -> list[dict]:
        r = await self._client.get(f"/events/{year}/simple")
        r.raise_for_status()
        events: list[dict] = r.json()
        return sorted(events, key=lambda e: e.get("start_date", ""))

    async def get_event_matches_with_videos(self, event_key: str) -> list[dict]:
        r = await self._client.get(f"/event/{event_key}/matches")
        r.raise_for_status()
        matches: list[dict] = r.json()
        with_video = [
            m for m in matches
            if any(v.get("type") == "youtube" for v in m.get("videos", []))
        ]
        level_order = {"qm": 0, "ef": 1, "qf": 2, "sf": 3, "f": 4}
        return sorted(
            with_video,
            key=lambda m: (level_order.get(m.get("comp_level", ""), 99), m.get("match_number", 0)),
        )

    async def get_match_teams(self, match_key: str) -> dict:
        r = await self._client.get(f"/match/{match_key}")
        r.raise_for_status()
        match = r.json()
        alliances = match.get("alliances", {})
        return {
            "red": alliances.get("red", {}).get("team_keys", []),
            "blue": alliances.get("blue", {}).get("team_keys", []),
        }

    async def get_match_youtube_key(self, match_key: str) -> str | None:
        r = await self._client.get(f"/match/{match_key}")
        r.raise_for_status()
        for video in r.json().get("videos", []):
            if video.get("type") == "youtube":
                return video.get("key")
        return None
