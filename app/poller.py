"""
Poller de plays: busca o estado mais recente do provider, filtra pelo
album-alvo, normaliza e persiste. Idempotente via UNIQUE constraint na
tabela play (rodar duas vezes em seguida nao duplica nada).

Usado por:
- Scheduler em background (a cada 15min, fase 10.4).
- Pode ser chamado on-demand depois de um login pra popular dado inicial.
"""

import asyncio
import logging

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.constants import POLL_INTERVAL_SECONDS
from app.db import engine
from app.lastfm_adapter import LastfmAPIError, get_recent_tracks
from app.models import Play, Provider, User
from app.play_normalizer import (
    is_target_lastfm_track,
    is_target_spotify_album,
    normalize_lastfm_play,
    normalize_spotify_play,
)
from app.spotify_for_user import TokenRevokedError, get_recently_played_for_user

logger = logging.getLogger(__name__)

# Spotify cap a 50 nesse endpoint. Pra Last.fm 50 cobre 15min de polling sobrando.
POLL_LIMIT = 50


async def poll_user(session: Session, user: User) -> int:
    """
    Persiste plays novos do user. Devolve quantos foram inseridos de fato
    (existentes batem na UNIQUE constraint e sao ignorados).

    Nao propaga excecoes do provider — loga e devolve 0. Esse comportamento
    e essencial pro scheduler: um user com token quebrado nao pode derrubar
    o poller dos outros.
    """
    try:
        plays = await _collect_plays(session, user)
    except TokenRevokedError:
        logger.warning(
            "poll_user: token revogado spotify=%s", user.provider_user_id
        )
        return 0
    except LastfmAPIError as e:
        logger.warning(
            "poll_user: lastfm error code=%s user=%s msg=%s",
            e.code, user.provider_user_id, e.message,
        )
        return 0
    except Exception:
        logger.exception(
            "poll_user: erro inesperado provider=%s user=%s",
            user.provider, user.provider_user_id,
        )
        return 0

    inserted = 0
    for play in plays:
        try:
            session.add(play)
            session.commit()
            inserted += 1
        except IntegrityError:
            # play ja existia — UNIQUE constraint funcionou, dedup OK
            session.rollback()
    return inserted


async def _collect_plays(session: Session, user: User) -> list[Play]:
    """
    Busca + filtra + normaliza. Devolve so plays prontos pra INSERT (ja
    filtrados pelo album-alvo).
    """
    if user.provider == Provider.SPOTIFY:
        raw = await get_recently_played_for_user(session, user)
        items = raw.get("items") or []
        return [
            normalize_spotify_play(item, user)
            for item in items
            if is_target_spotify_album(item)
        ]

    if user.provider == Provider.LASTFM:
        raw = await get_recent_tracks(user.provider_user_id, limit=POLL_LIMIT)
        tracks = (raw.get("recenttracks") or {}).get("track") or []
        plays: list[Play] = []
        for t in tracks:
            if not is_target_lastfm_track(t):
                continue
            p = normalize_lastfm_play(t, user)
            if p is not None:
                plays.append(p)
        return plays

    return []


async def poll_all_users() -> None:
    """
    Roda poll_user em paralelo pra todos os users do banco. Cada user usa
    uma Session propria pra evitar contention de transacao no SQLite e pra
    isolar erros (rollback de um nao afeta os outros).

    Excecoes individuais sao silenciadas dentro do poll_user, mas mesmo
    assim usamos return_exceptions=True como rede de seguranca.
    """
    with Session(engine) as session:
        users = list(session.exec(select(User)).all())

    if not users:
        return

    async def _poll_with_own_session(u: User) -> int:
        with Session(engine) as s:
            return await poll_user(s, u)

    results = await asyncio.gather(
        *(_poll_with_own_session(u) for u in users),
        return_exceptions=True,
    )

    total_inserted = sum(r for r in results if isinstance(r, int))
    failures = [r for r in results if isinstance(r, Exception)]
    # Log o exception real de cada falha — gather(return_exceptions=True) engole
    # o traceback se a gente so contar. Sem isso, depurar "porque tal play nao
    # entrou" vira advinhacao.
    for user, result in zip(users, results):
        if isinstance(result, Exception):
            logger.error(
                "poll_all_users: user provider=%s id=%s falhou: %r",
                user.provider, user.provider_user_id, result,
            )
    logger.info(
        "poll_all_users: users=%d inserted=%d failures=%d",
        len(users), total_inserted, len(failures),
    )


async def poller_loop() -> None:
    """
    Loop infinito que roda poll_all_users a cada POLL_INTERVAL_SECONDS.
    Resiliente: qualquer Exception e logada e o loop continua. Apenas
    asyncio.CancelledError (que e BaseException, nao Exception) propaga
    e termina o loop — usado pelo lifespan no shutdown.
    """
    logger.info("poller_loop: iniciando (interval=%ds)", POLL_INTERVAL_SECONDS)
    while True:
        try:
            await poll_all_users()
        except Exception:
            logger.exception("poller_loop: poll_all_users falhou")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
