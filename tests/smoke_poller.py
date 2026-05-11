"""
Smoke test: roda poll_user pra todos os users do banco e mostra quantos
plays novos foram inseridos por user.

Pre-requisito: pelo menos 1 user logado (Spotify ou Last.fm) que ja tenha
ouvido alguma track do album-alvo recentemente.

Uso:
    uv run python tests/smoke_poller.py

Roda 2x em sequencia pra validar dedup: a 1a deve inserir, a 2a deve
inserir 0 (UNIQUE constraint pegando).
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func
from sqlmodel import Session, select

from app.db import engine
from app.models import Play, User
from app.poller import poll_user


async def main():
    print("=" * 60)
    print("SMOKE POLLER — rodada 1 (deve inserir)")
    print("=" * 60)
    await _run_round()

    print()
    print("=" * 60)
    print("SMOKE POLLER — rodada 2 (deve inserir 0, dedup)")
    print("=" * 60)
    await _run_round()

    print()
    print("=" * 60)
    print("CONTAGEM TOTAL POR USER")
    print("=" * 60)
    with Session(engine) as session:
        users = session.exec(select(User)).all()
        for u in users:
            count = len(session.exec(
                select(Play)
                .where(Play.provider == u.provider)
                .where(Play.provider_user_id == u.provider_user_id)
            ).all())
            print(f"  {u.provider.value:8s} {u.provider_user_id:30s} -> {count} plays")

    print()
    print("=" * 60)
    print("TOP TRACKS (todos os users somados)")
    print("=" * 60)
    with Session(engine) as session:
        rows = session.exec(
            select(
                Play.track_key,
                Play.track_name,
                Play.artists,
                func.count().label("plays"),
            )
            .group_by(Play.track_key, Play.track_name, Play.artists)
            .order_by(func.count().desc())
        ).all()
        if not rows:
            print("  (nenhum play registrado)")
        for i, row in enumerate(rows, start=1):
            print(f"  {i:2d}. {row.plays:3d}x  {row.track_name} - {row.artists}")

    print()
    print("=" * 60)
    print("BREAKDOWN POR USER x TRACK")
    print("=" * 60)
    with Session(engine) as session:
        rows = session.exec(
            select(
                Play.provider,
                Play.provider_user_id,
                Play.track_name,
                func.count().label("plays"),
            )
            .group_by(
                Play.provider, Play.provider_user_id,
                Play.track_key, Play.track_name,
            )
            .order_by(
                Play.provider_user_id,
                func.count().desc(),
            )
        ).all()
        if not rows:
            print("  (nenhum play registrado)")
        current_user = None
        for row in rows:
            user_key = (row.provider, row.provider_user_id)
            if user_key != current_user:
                print(f"\n  [{row.provider.value}] {row.provider_user_id}")
                current_user = user_key
            print(f"     {row.plays:3d}x  {row.track_name}")


async def _run_round():
    with Session(engine) as session:
        users = session.exec(select(User)).all()
        if not users:
            print("  (nenhum user no banco — faca login primeiro)")
            return
        for u in users:
            n = await poll_user(session, u)
            print(f"  {u.provider.value:8s} {u.provider_user_id:30s} -> +{n} plays")


if __name__ == "__main__":
    asyncio.run(main())
