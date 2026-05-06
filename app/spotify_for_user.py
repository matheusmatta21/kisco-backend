from datetime import datetime, timedelta, timezone

import httpx
from sqlmodel import Session

from app import spotify_adapter
from app.constants import TOKEN_REFRESH_MARGIN_SECONDS
from app.models import User


class TokenRevokedError(Exception):
    def __init__(self, spotify_id: str):
        self.spotify_id = spotify_id
        super().__init__(f"Token do usuário {spotify_id} foi revogado.")


async def _refresh_and_persist(session: Session, user: User) -> None:
    try:
        new_tokens = await spotify_adapter.refresh_access_token(user.refresh_token)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            raise TokenRevokedError(user.spotify_id) from e
        raise

    now = datetime.now(timezone.utc)
    user.access_token = new_tokens["access_token"]
    if "refresh_token" in new_tokens:
        user.refresh_token = new_tokens["refresh_token"]
    user.token_expires_at = now + timedelta(seconds=new_tokens["expires_in"])
    user.updated_at = now
    session.commit()


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


async def ensure_fresh_token(session: Session, user: User) -> str:
    now = datetime.now(timezone.utc)
    margin = timedelta(seconds=TOKEN_REFRESH_MARGIN_SECONDS)
    if _as_utc(user.token_expires_at) - margin <= now:
        await _refresh_and_persist(session, user)
    return user.access_token


async def get_recently_played_for_user(session: Session, user: User) -> dict:
    await ensure_fresh_token(session, user)
    try:
        return await spotify_adapter.get_recently_played(user.access_token)
    except httpx.HTTPStatusError as e:
        if e.response.status_code != 401:
            raise
        await _refresh_and_persist(session, user)
        return await spotify_adapter.get_recently_played(user.access_token)


def filter_tracks_by_album(recently_played: dict, album_id: str) -> list[dict]:
    items = recently_played.get("items", [])
    return [
        item
        for item in items
        if item.get("track", {}).get("album", {}).get("id") == album_id
    ]
