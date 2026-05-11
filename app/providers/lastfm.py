from datetime import datetime, timezone

from sqlmodel import Session

from app.constants import ALBUM_NAME_LASTFM, ARTIST_NAME_LASTFM, LASTFM_RECENT_MAX_LIMIT
from app.lastfm_adapter import LastfmAPIError, get_recent_tracks
from app.models import User


def _played_at_iso(track: dict) -> str:
    nowplaying = track.get("@attr", {}).get("nowplaying") == "true"
    if nowplaying:
        return datetime.now(timezone.utc).isoformat()

    uts = track.get("date", {}).get("uts")
    if uts:
        return datetime.fromtimestamp(int(uts), tz=timezone.utc).isoformat()

    return datetime.now(timezone.utc).isoformat()


def _format_track(t: dict) -> dict:
    images = t.get("image", []) or []
    image_url = next(
        (img["#text"] for img in images
         if img.get("size") == "extralarge" and img.get("#text")),
        None,
    )
    artist_text = t.get("artist", {}).get("#text", "")
    return {
        "name": t.get("name", ""),
        "artists": [artist_text] if artist_text else [],
        "played_at": _played_at_iso(t),
        "album_name": t.get("album", {}).get("#text", ""),
        "image_url": image_url,
    }


def _matches_target_album(track: dict, target_album: str, target_artist: str) -> bool:
    album = track.get("album", {}).get("#text", "").strip().casefold()
    artist = track.get("artist", {}).get("#text", "").strip().casefold()
    return album == target_album and artist == target_artist


class LastfmProvider:
    async def fetch_recent_for_album(
        self, session: Session, user: User, limit: int
    ) -> list[dict] | None:
        try:
            data = await get_recent_tracks(
                user.provider_user_id, limit=LASTFM_RECENT_MAX_LIMIT
            )
        except LastfmAPIError:
            return []

        tracks = data.get("recenttracks", {}).get("track", [])
        target_album = ALBUM_NAME_LASTFM.strip().casefold()
        target_artist = ARTIST_NAME_LASTFM.strip().casefold()
        matches = [
            t for t in tracks
            if _matches_target_album(t, target_album, target_artist)
        ][:limit]
        return [_format_track(t) for t in matches]
