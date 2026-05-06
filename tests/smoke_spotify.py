"""
Smoke test manual do spotify_adapter.

Pré-requisito: rodar `scripts/print_auth_url.py`, abrir a URL no browser,
autorizar, e copiar o `code` da URL de redirect.

Uso:
    uv run python scripts/smoke_spotify.py <code>
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.spotify_adapter import (
    exchange_code_for_tokens,
    get_recently_played,
    get_user_profile,
    refresh_access_token,
)


def pretty(label: str, data) -> None:
    print(f"\n=== {label} ===")
    text = json.dumps(data, indent=2, ensure_ascii=False)
    print(text[:1500])


async def main(code: str) -> None:
    print(">>> 1. Trocando code por tokens...")
    tokens = await exchange_code_for_tokens(code)
    pretty("tokens (resumo)", {
        "access_token": tokens["access_token"][:30] + "...",
        "refresh_token": tokens["refresh_token"][:30] + "...",
        "expires_in": tokens["expires_in"],
        "scope": tokens.get("scope"),
        "token_type": tokens.get("token_type"),
    })
    access = tokens["access_token"]
    refresh = tokens["refresh_token"]

    print("\n>>> 2. Buscando perfil...")
    profile = await get_user_profile(access)
    pretty("profile (campos do User)", {
        "id": profile.get("id"),
        "display_name": profile.get("display_name"),
        "first_image_url": (profile.get("images") or [{}])[0].get("url"),
    })

    print("\n>>> 3. Buscando histórico recente (limit=10)...")
    recent = await get_recently_played(access, limit=10)
    items = recent.get("items", [])
    print(f"items recebidos: {len(items)}")
    if items:
        first = items[0]
        pretty("primeira track", {
            "name": first["track"]["name"],
            "album_id": first["track"]["album"]["id"],
            "album_name": first["track"]["album"]["name"],
            "played_at": first["played_at"],
        })

    print("\n>>> 4. Refrescando access token...")
    new_tokens = await refresh_access_token(refresh)
    pretty("novos tokens", {
        "access_token_changed": new_tokens["access_token"] != access,
        "expires_in": new_tokens.get("expires_in"),
        "refresh_token_veio_na_resposta?": "refresh_token" in new_tokens,
    })

    print("\nOK — todas as 4 funcoes responderam sem excecao.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("uso: uv run python scripts/smoke_spotify.py <code>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
