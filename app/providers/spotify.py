from sqlmodel import Session

from app.constants import ALBUM_ID
from app.models import User
from app.spotify_for_user import (
    TokenRevokedError,
    filter_tracks_by_album,
    get_recently_played_for_user,
)


def _format_track(item: dict) -> dict:
    track = item["track"]
    images = track["album"].get("images") or []
    return {
        "name": track["name"],
        "artists": [artist["name"] for artist in track.get("artists", [])],
        "played_at": item["played_at"], 
        "album_name": track["album"]["name"],
        "image_url": images[0]["url"] if images else None,
    }


class SpotifyProvider:
    async def fetch_recent_for_album(
        self, session: Session, user: User, limit: int
    ) -> list[dict] | None:
        try:
            played = await get_recently_played_for_user(session, user)
        except TokenRevokedError:
            return None  # esconder card; user precisa re-autenticar
        matches = filter_tracks_by_album(played, ALBUM_ID)[:limit]
        return [_format_track(item) for item in matches]
