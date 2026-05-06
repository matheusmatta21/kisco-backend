"""
Lista todos os usuários persistidos no banco.

Uso:
    uv run python tests/list_users.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, select

from app.db import engine
from app.models import User


def _trunc(value: str | None, n: int = 12) -> str:
    if not value:
        return "<none>"
    if len(value) <= n:
        return value
    return value[:n] + "..."


def main() -> None:
    with Session(engine) as session:
        users = list(session.exec(select(User)))

    if not users:
        print("Nenhum usuário no banco. Faça login via /auth/spotify primeiro.")
        return

    print(f"Total de usuários: {len(users)}\n")
    for i, user in enumerate(users, start=1):
        print(f"[{i}] spotify_id       : {user.spotify_id}")
        print(f"    display_name     : {user.display_name}")
        print(f"    token_expires_at : {user.token_expires_at}")
        print(f"    access_token     : {_trunc(user.access_token)}")
        print(f"    refresh_token    : {_trunc(user.refresh_token)}")
        print(f"    created_at       : {user.created_at}")
        print(f"    updated_at       : {user.updated_at}")
        print()


if __name__ == "__main__":
    main()
