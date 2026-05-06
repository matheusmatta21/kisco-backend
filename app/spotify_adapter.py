import httpx

from app.config import settings
from app.constants import RECENTLY_PLAYED_MAX_LIMIT, SPOTIFY_API_BASE, SPOTIFY_TOKEN_URL


def _basic_auth() -> httpx.BasicAuth:
    return httpx.BasicAuth(
        username=settings.SPOTIFY_CLIENT_ID, password=settings.SPOTIFY_CLIENT_SECRET
    )


async def exchange_code_for_tokens(code: str) -> dict:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.SPOTIFY_REDIRECT_URI,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(SPOTIFY_TOKEN_URL, data=data, auth=_basic_auth())
        response.raise_for_status()
        return response.json()


async def refresh_access_token(refresh_token: str) -> dict:
    data = {"grant_type": "refresh_token", "refresh_token": refresh_token}
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(SPOTIFY_TOKEN_URL, data=data, auth=_basic_auth())
        response.raise_for_status()
        return response.json()


async def get_user_profile(access_token: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{SPOTIFY_API_BASE}/me", headers=headers)
        response.raise_for_status()
        return response.json()


async def get_recently_played(
    access_token: str, limit: int = RECENTLY_PLAYED_MAX_LIMIT
) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"limit": limit}
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{SPOTIFY_API_BASE}/me/player/recently-played",
            headers=headers,
            params=params,
        )
        response.raise_for_status()
        return response.json()
