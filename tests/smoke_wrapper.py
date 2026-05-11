"""
Smoke test do wrapper de token (app/spotify_for_user.py).

Cenarios cobertos:
  1. Refresh proativo: forca token_expires_at no passado, valida que o
     wrapper renova antes de chamar a API.
  2. Caminho feliz: retorna recently-played sem erro.
  3. Filtro: aplica filter_tracks_by_album e mostra os matches.

Tratamento explicito de TokenRevokedError.

Uso:
    uv run python tests/smoke_wrapper.py
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, select

from app.constants import ALBUM_ID
from app.db import engine
from app.models import User
from app.spotify_for_user import (
    TokenRevokedError,
    filter_tracks_by_album,
    get_recently_played_for_user,
)


def _trunc(value: str | None, n: int = 12) -> str:
    if not value:
        return "<none>"
    return value[:n] + "..." if len(value) > n else value


def _print_track(idx: int, item: dict) -> None:
    track = item.get("track", {}) or {}
    name = track.get("name", "<sem nome>")
    artists = ", ".join(a.get("name", "?") for a in track.get("artists", []))
    played_at = item.get("played_at", "?")
    print(f"  [{idx}] {name} - {artists}  (played_at={played_at})")


async def main() -> None:
    with Session(engine) as session:
        user = session.exec(select(User)).first()
        if user is None:
            print("Nenhum usuario no banco. Faca login via /auth/spotify primeiro.")
            return

        print(f"User alvo: {user.provider_user_id} ({user.display_name})")
        print(f"  token_expires_at (antes): {user.token_expires_at}")
        print(f"  access_token    (antes): {_trunc(user.access_token)}")
        print()

        forced_past = datetime.now(timezone.utc) - timedelta(hours=1)
        user.token_expires_at = forced_past
        session.add(user)
        session.commit()
        session.refresh(user)
        print(f"Forcado token_expires_at = {user.token_expires_at} (passado)")
        print("Chamando get_recently_played_for_user (deve disparar refresh proativo)...\n")

        try:
            recently_played = await get_recently_played_for_user(session, user)
        except TokenRevokedError as e:
            print(f"TokenRevokedError: user {e.spotify_id} revogou o app no Spotify.")
            print("Reautorize via /auth/spotify e rode de novo.")
            return

        session.refresh(user)
        expires_at = user.token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        print(f"  token_expires_at (depois): {expires_at}")
        print(f"  access_token    (depois): {_trunc(user.access_token)}")
        if expires_at > datetime.now(timezone.utc):
            print("  -> Refresh proativo funcionou (expira no futuro).")
        else:
            print("  -> ALERTA: token_expires_at ainda no passado.")
        print()

        items = recently_played.get("items", [])
        print(f"Recently-played: {len(items)} tracks no total.")
        for i, item in enumerate(items[:50], start=1):
            _print_track(i, item)
        print()

        matches = filter_tracks_by_album(recently_played, ALBUM_ID)
        print(f"Tracks do album {ALBUM_ID}: {len(matches)} match(es).")
        for i, item in enumerate(matches, start=1):
            _print_track(i, item)


if __name__ == "__main__":
    asyncio.run(main())
