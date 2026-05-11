from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import ForeignKeyConstraint, Index, UniqueConstraint
from sqlmodel import SQLModel, Field


class Provider(str, Enum):
    SPOTIFY = "spotify"
    LASTFM = "lastfm"


class User(SQLModel, table=True):

    provider: Provider = Field(primary_key=True)
    provider_user_id: str = Field(primary_key=True)

    display_name: str
    avatar_url: str | None = None

    #token do spotify
    access_token: str | None = None
    refresh_token: str | None = None
    token_expires_at: datetime | None = None

    lastfm_session_key: str | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Play(SQLModel, table=True):
    """
    Registro de uma execução individual (scrobble/play) capturada via poller.

    track_key: f"{first_artist}::{track_name}".casefold() — chave de comparação
    cross-provider (mesma música no Spotify e Last.fm cai na mesma chave).
    played_at: sempre UTC, precisão de segundo.
    Dedup: unique (provider, provider_user_id, played_at, track_key) — o poller
    pode reinserir sem medo, conflitos viram IntegrityError e a gente ignora.
    """

    id: int | None = Field(default=None, primary_key=True)

    provider: Provider
    provider_user_id: str

    played_at: datetime
    track_key: str

    track_name: str
    artists: str
    album_name: str
    image_url: str | None = None

    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_user_id", "played_at", "track_key",
            name="uq_play_dedup",
        ),
        Index("ix_play_user_played", "provider", "provider_user_id", "played_at"),
        Index("ix_play_album_played", "album_name", "played_at"),
        Index("ix_play_track_played", "track_key", "played_at"),
        ForeignKeyConstraint(
            ["provider", "provider_user_id"],
            ["user.provider", "user.provider_user_id"],
        ),
    )
