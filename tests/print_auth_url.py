"""
Imprime a URL de autorização do Spotify pra rodar o fluxo OAuth manualmente.

Uso:
    uv run python tests/print_auth_url.py

Depois: cole a URL no browser, autorize, copie o `code` da URL de redirect.
"""
import sys
from pathlib import Path
from urllib.parse import quote, urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.constants import SPOTIFY_AUTHORIZE_URL, SPOTIFY_SCOPES


def main():
    params = {
        "client_id": settings.SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": settings.SPOTIFY_REDIRECT_URI,
        "scope": SPOTIFY_SCOPES,
        "state": "smoketest123",
        "show_dialog": "true",
    }
    url = f"{SPOTIFY_AUTHORIZE_URL}?{urlencode(params, quote_via=quote)}"
    print("Abra esta URL no browser:\n")
    print(url)
    print("\nDepois de autorizar, copie o valor de `code=...` da URL de redirect.")


if __name__ == "__main__":
    main()
