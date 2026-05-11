from typing import Protocol

from sqlmodel import Session

from app.models import User


class MusicProvider(Protocol):
    """
    Interface comum pra cada plataforma de musica integrada (Spotify, Last.fm, ...).

    fetch_recent_for_album devolve uma lista de tracks ja filtradas pelo album-alvo
    do KISCO e normalizadas pro shape do TrackOut (name, artists, played_at ISO8601,
    album_name, image_url).

    Retorna None quando o user esta em estado autenticadamente quebrado e o card
    deve ser escondido (ex: token revogado no Spotify). Lista vazia [] significa
    "user OK, mas nao tem tracks do album". O caller filtra Nones do resultado.
    """

    async def fetch_recent_for_album(
        self, session: Session, user: User, limit: int
    ) -> list[dict] | None: ...
