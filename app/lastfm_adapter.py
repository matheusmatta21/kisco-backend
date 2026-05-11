import hashlib
import httpx
from app.config import settings
from app.constants import LASTFM_API_BASE


class LastfmAPIError(Exception):
    """
    Last.fm devolve {"error": N, "message": "..."} no corpo em virtualmente todos
    os erros — as vezes com HTTP 200, as vezes com 4xx (api key invalida vem como
    403, rate limit como 429, etc). O adapter normaliza tudo via essa exception
    em vez de deixar o caller diferenciar httpx.HTTPStatusError de erro de API.

    Codigos comuns: 4 auth failed, 9 invalid session, 10 invalid api key,
    14 token nao autorizado, 15 token expirado, 16 service offline,
    26 api key suspensa, 29 rate limit.
    """

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"Last.fm API error {code}: {message}")


def _parse_lastfm_response(resp: httpx.Response) -> dict:
    """
    Tenta parsear JSON antes de checar HTTP status, porque o Last.fm coloca
    {error, message} no corpo mesmo em respostas 4xx. Se o body tiver `error`,
    levanta LastfmAPIError. Caso contrario, deixa raise_for_status decidir.
    """
    try:
        data = resp.json()
    except ValueError:
        # Resposta nao-JSON (ex: HTML de pagina de erro). Cai pro fallback HTTP.
        resp.raise_for_status()
        raise  # se HTTP era OK mas o body nao era JSON, propaga ValueError

    if isinstance(data, dict) and "error" in data:
        try:
            code = int(data.get("error", 0))
        except (TypeError, ValueError):
            code = 0
        raise LastfmAPIError(code=code, message=str(data.get("message", "")))

    resp.raise_for_status()
    return data


def _sign(params: dict[str, str]) -> str:
    filtered = {k: v for k, v in params.items() if k not in ("format", "callback")}
    concat = "".join(f"{k}{filtered[k]}" for k in sorted(filtered))
    concat += settings.LASTFM_SHARED_SECRET
    return hashlib.md5(concat.encode("utf-8")).hexdigest()


async def exchange_token_for_session(token: str) -> dict:
    params = {
        "method": "auth.getSession",
        "api_key": settings.LASTFM_API_KEY,
        "token": token,
    }
    params["api_sig"] = _sign(params)
    params["format"] = "json"

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(LASTFM_API_BASE, params=params)
        return _parse_lastfm_response(resp)  # {"session": {"name": ..., "key": ..., "subscriber": ...}}


async def get_user_info(username: str) -> dict:
    params = {
        "method": "user.getInfo",
        "user": username,
        "api_key": settings.LASTFM_API_KEY,
        "format": "json",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(LASTFM_API_BASE, params=params)
        return _parse_lastfm_response(resp)


async def get_recent_tracks(username: str, limit: int = 50) -> dict:
    params = {
        "method": "user.getRecentTracks",
        "user": username,
        "api_key": settings.LASTFM_API_KEY,
        "limit": str(limit),
        "extended": "0",
        "format": "json",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(LASTFM_API_BASE, params=params)
        return _parse_lastfm_response(resp)
