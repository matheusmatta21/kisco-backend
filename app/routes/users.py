import asyncio

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from app.constants import TRACKS_PER_USER
from app.db import get_session
from app.models import User
from app.providers import PROVIDERS


class TrackOut(BaseModel):
    name: str
    artists: list[str]
    played_at: str
    album_name: str
    image_url: str | None


class UserOut(BaseModel):
    provider: str
    provider_user_id: str
    display_name: str
    avatar_url: str | None
    tracks: list[TrackOut]


class UsersResponse(BaseModel):
    users: list[UserOut]


router = APIRouter(tags=["users"])


async def _build_user_payload(session: Session, user: User) -> dict | None:
    provider = PROVIDERS.get(user.provider)
    if provider is None:
        return None  # provider desconhecido — ignora silenciosamente

    tracks = await provider.fetch_recent_for_album(session, user, TRACKS_PER_USER)
    if tracks is None:
        return None  # provider sinalizou que o user esta quebrado (ex: token revogado)

    return {
        "provider": user.provider,
        "provider_user_id": user.provider_user_id,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "tracks": tracks,
    }


@router.get("", response_model=UsersResponse)
async def list_users(session: Session = Depends(get_session)):
    users = session.exec(select(User)).all()

    results = await asyncio.gather(
        *(_build_user_payload(session, u) for u in users), return_exceptions=True
    )

    final = [r for r in results if r is not None and not isinstance(r, Exception)]
    return {"users": final}
