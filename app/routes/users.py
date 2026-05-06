import asyncio
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from app.constants import ALBUM_ID, TRACKS_PER_USER
from app.db import get_session
from app.models import User
from app.spotify_for_user import (
    TokenRevokedError,
    filter_tracks_by_album,
    get_recently_played_for_user,
)


class TrackOut(BaseModel):
    name: str
    artists: list[str]
    played_at: str
    album_name: str
    image_url: str | None


class UserOut(BaseModel):
    spotify_id: str
    display_name: str
    avatar_url: str | None
    tracks: list[TrackOut]


class UsersResponse(BaseModel):
    users: list[UserOut]


router = APIRouter(tags=["users"])


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


async def _build_user_payload(session: Session, user: User) -> dict | None:
    try:
        played = await get_recently_played_for_user(session, user)
    except TokenRevokedError:
        return None
    matches = filter_tracks_by_album(played, ALBUM_ID)[:TRACKS_PER_USER]
    return {
        "spotify_id": user.spotify_id,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "tracks": [_format_track(item) for item in matches],
    }


@router.get("", response_model=UsersResponse)
async def list_users(session: Session = Depends(get_session)):
    users = session.exec(select(User)).all()

    results = await asyncio.gather(
        *(_build_user_payload(session, u) for u in users), return_exceptions=True
    )

    final = [r for r in results if r is not None and not isinstance(r, Exception)]
    return {"users": final}
