"""
Smoke test manual do lastfm_adapter.

Usa a conta publica oficial 'rj' (Richard Jones, fundador do Last.fm) por
default, mas aceita qualquer username via argumento.

Valida que:
  1. LASTFM_API_KEY no .env esta correta (chamadas nao retornam error 10).
  2. user.getInfo parseia (avatar, realname).
  3. user.getRecentTracks parseia (lista de tracks com artist/album/name).

Uso:
    uv run python tests/smoke_lastfm.py            # usa 'rj'
    uv run python tests/smoke_lastfm.py <username> # usa outro user
"""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_env_prod = ROOT / ".env.prod"
if _env_prod.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_prod, override=True)
    print(f"[smoke_lastfm] carregando vars de {_env_prod.name}")

from app.lastfm_adapter import LastfmAPIError, get_recent_tracks, get_user_info


def pretty(label: str, data) -> None:
    print(f"\n=== {label} ===")
    text = json.dumps(data, indent=2, ensure_ascii=False)
    print(text[:1500])


async def main(username: str) -> None:
    print(f">>> Usuario alvo: {username}\n")

    print(">>> 1. Buscando user.getInfo...")
    try:
        info = await get_user_info(username)
    except LastfmAPIError as e:
        print(f"[getInfo] {e}")
        return
    user = info.get("user", {})
    images = user.get("image", [])
    avatar = next(
        (img["#text"] for img in images if img.get("size") == "extralarge" and img.get("#text")),
        None,
    )
    pretty("user (campos relevantes)", {
        "name": user.get("name"),
        "realname": user.get("realname"),
        "country": user.get("country"),
        "playcount": user.get("playcount"),
        "avatar_extralarge": avatar,
    })

    print("\n>>> 2. Buscando recently played (limit=10)...")
    try:
        recent = await get_recent_tracks(username, limit=10)
    except LastfmAPIError as e:
        print(f"[getRecentTracks] {e}")
        return

    tracks = recent.get("recenttracks", {}).get("track", [])
    print(f"tracks recebidas: {len(tracks)}")

    if tracks:
        first = tracks[0]
        nowplaying = first.get("@attr", {}).get("nowplaying") == "true"
        pretty("primeira track", {
            "name": first.get("name"),
            "artist": first.get("artist", {}).get("#text"),
            "album": first.get("album", {}).get("#text"),
            "album_mbid": first.get("album", {}).get("mbid") or "<vazio>",
            "nowplaying": nowplaying,
            "played_at_uts": first.get("date", {}).get("uts") if not nowplaying else "<n/a>",
        })

        print("\n>>> 3. Lista resumida das tracks recentes:")
        for i, t in enumerate(tracks, start=1):
            artist = t.get("artist", {}).get("#text", "?")
            name = t.get("name", "?")
            album = t.get("album", {}).get("#text", "")
            album_str = f"  [{album}]" if album else ""
            np = " (now playing)" if t.get("@attr", {}).get("nowplaying") == "true" else ""
            print(f"  [{i}] {name} - {artist}{album_str}{np}")

    print("\nOK — todas as 2 funcoes responderam sem excecao.")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) >= 2 else "rj"
    asyncio.run(main(target))
