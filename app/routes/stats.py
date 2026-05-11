from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import case, func
from sqlmodel import Session, select

from app.db import get_session
from app.models import Play, Provider, User

Period = Literal["week", "month", "total"]


class StatsUser(BaseModel):
    provider: str
    provider_user_id: str
    display_name: str
    avatar_url: str | None


class TrackInfo(BaseModel):
    track_key: str
    track_name: str
    artists: str
    image_url: str | None


class StatsWindow(BaseModel):
    period: Period
    window_start: datetime
    window_end: datetime


class TopListenerResponse(StatsWindow):
    user: StatsUser | None
    play_count: int


class TopTrackResponse(StatsWindow):
    track: TrackInfo | None
    play_count: int


class RankingEntry(BaseModel):
    rank: int
    user: StatsUser
    play_count: int


class RankingResponse(StatsWindow):
    ranking: list[RankingEntry]


class TopTrackEntry(BaseModel):
    rank: int
    track: TrackInfo
    play_count: int


class TopTracksResponse(StatsWindow):
    tracks: list[TopTrackEntry]


router = APIRouter(tags=["stats"])


def _resolve_window(session: Session, period: Period) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    if period == "total":
        earliest = session.exec(select(func.min(Play.played_at))).first()
        if earliest is None:
            return now, now
        if earliest.tzinfo is None:
            earliest = earliest.replace(tzinfo=timezone.utc)
        return earliest, now
    days = 7 if period == "week" else 30
    return now - timedelta(days=days), now


def _stats_user(session: Session, provider, provider_user_id: str) -> StatsUser:
    u = session.get(User, (provider, provider_user_id))
    return StatsUser(
        provider=provider.value if hasattr(provider, "value") else str(provider),
        provider_user_id=provider_user_id,
        display_name=u.display_name if u else "(usuario removido)",
        avatar_url=u.avatar_url if u else None,
    )


@router.get("/top-listener", response_model=TopListenerResponse)
async def top_listener(
    period: Period = "week",
    session: Session = Depends(get_session),
):
    start, end = _resolve_window(session, period)

    row = session.exec(
        select(
            Play.provider,
            Play.provider_user_id,
            func.count().label("plays"),
        )
        .where(Play.played_at >= start)
        .group_by(Play.provider, Play.provider_user_id)
        .order_by(func.count().desc())
        .limit(1)
    ).first()

    if row is None:
        return TopListenerResponse(
            period=period,
            window_start=start,
            window_end=end,
            user=None,
            play_count=0,
        )

    return TopListenerResponse(
        period=period,
        window_start=start,
        window_end=end,
        user=_stats_user(session, row.provider, row.provider_user_id),
        play_count=row.plays,
    )


@router.get("/top-track", response_model=TopTrackResponse)
async def top_track(
    period: Period = "week",
    session: Session = Depends(get_session),
):
    start, end = _resolve_window(session, period)

    row = session.exec(
        select(
            Play.track_key,
            func.max(Play.track_name).label("track_name"),
            func.max(Play.artists).label("artists"),
            func.coalesce(
                func.max(case((Play.provider == Provider.SPOTIFY, Play.image_url))),
                func.max(Play.image_url),
            ).label("image_url"),
            func.count().label("plays"),
        )
        .where(Play.played_at >= start)
        .group_by(Play.track_key)
        .order_by(func.count().desc())
        .limit(1)
    ).first()

    if row is None:
        return TopTrackResponse(
            period=period,
            window_start=start,
            window_end=end,
            track=None,
            play_count=0,
        )

    return TopTrackResponse(
        period=period,
        window_start=start,
        window_end=end,
        track=TrackInfo(
            track_key=row.track_key,
            track_name=row.track_name,
            artists=row.artists,
            image_url=row.image_url,
        ),
        play_count=row.plays,
    )


@router.get("/top-tracks", response_model=TopTracksResponse)
async def top_tracks(
    period: Period = "week",
    limit: int = Query(default=10, ge=1, le=50),
    session: Session = Depends(get_session),
):
    """Top N tracks do album somando todos os users (cross-provider)."""
    start, end = _resolve_window(session, period)

    rows = session.exec(
        select(
            Play.track_key,
            func.max(Play.track_name).label("track_name"),
            func.max(Play.artists).label("artists"),
            func.coalesce(
                func.max(case((Play.provider == Provider.SPOTIFY, Play.image_url))),
                func.max(Play.image_url),
            ).label("image_url"),
            func.count().label("plays"),
        )
        .where(Play.played_at >= start)
        .group_by(Play.track_key)
        .order_by(func.count().desc())
        .limit(limit)
    ).all()

    entries = [
        TopTrackEntry(
            rank=i,
            track=TrackInfo(
                track_key=r.track_key,
                track_name=r.track_name,
                artists=r.artists,
                image_url=r.image_url,
            ),
            play_count=r.plays,
        )
        for i, r in enumerate(rows, start=1)
    ]

    return TopTracksResponse(
        period=period,
        window_start=start,
        window_end=end,
        tracks=entries,
    )


@router.get("/ranking", response_model=RankingResponse)
async def ranking(
    period: Period = "week",
    limit: int = Query(default=10, ge=1, le=50),
    session: Session = Depends(get_session),
):
    start, end = _resolve_window(session, period)

    rows = session.exec(
        select(
            Play.provider,
            Play.provider_user_id,
            func.count().label("plays"),
        )
        .where(Play.played_at >= start)
        .group_by(Play.provider, Play.provider_user_id)
        .order_by(func.count().desc())
        .limit(limit)
    ).all()

    entries = [
        RankingEntry(
            rank=i,
            user=_stats_user(session, r.provider, r.provider_user_id),
            play_count=r.plays,
        )
        for i, r in enumerate(rows, start=1)
    ]

    return RankingResponse(
        period=period,
        window_start=start,
        window_end=end,
        ranking=entries,
    )
