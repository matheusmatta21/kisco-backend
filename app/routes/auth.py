import httpx
import secrets
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from itsdangerous import URLSafeSerializer, BadSignature
from pydantic import BaseModel
from sqlmodel import Session
from urllib.parse import quote, urlencode

from app.config import settings
from app.constants import LASTFM_AUTH_URL, SPOTIFY_AUTHORIZE_URL, SPOTIFY_SCOPES
from app.db import get_session
from app.models import Provider, User
from app import lastfm_adapter, lastfm_for_user, spotify_adapter, spotify_for_user

router = APIRouter(tags=["auth"])

OAUTH_STATE_COOKIE = "oauth_state"
STATE_COOKIE_MAX_AGE = 600  # 10min

SESSION_COOKIE = "kisco_session"
SESSION_COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 dias


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(settings.SESSION_SECRET, salt="oauth-state")


def _session_serializer() -> URLSafeSerializer:
    return URLSafeSerializer(settings.SESSION_SECRET, salt="kisco-session")


def _cookie_security_kwargs() -> dict:
    # Cross-site (Vercel → Fly) exige SameSite=None + Secure. Em dev (HTTP no
    # 127.0.0.1) o browser rejeita Secure, então caímos pra Lax sem Secure.
    if settings.FRONTEND_URL.startswith("https://"):
        return {"secure": True, "samesite": "none"}
    return {"secure": False, "samesite": "lax"}


class MeResponse(BaseModel):
    provider: str
    provider_user_id: str
    display_name: str
    avatar_url: str | None


@router.get("/spotify")
async def start_spotify_auth():
    state = secrets.token_urlsafe(32)
    signed_state = _serializer().dumps(state)
    params = {
        "client_id": settings.SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": settings.SPOTIFY_REDIRECT_URI,
        "scope": SPOTIFY_SCOPES,
        "state": state,  # versão crua — Spotify devolve isso de volta
        "show_dialog": "true",  # força tela de consentimento (permite trocar de conta)
    }
    authorize_url = f"{SPOTIFY_AUTHORIZE_URL}?{urlencode(params, quote_via=quote)}"

    redirect = RedirectResponse(url=authorize_url, status_code=303)
    redirect.set_cookie(
        key=OAUTH_STATE_COOKIE,
        value=signed_state,
        max_age=STATE_COOKIE_MAX_AGE,
        httponly=True,
        **_cookie_security_kwargs(),
    )
    return redirect


@router.get("/callback")
async def spotify_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    session: Session = Depends(get_session),
):
    if error:
        raise HTTPException(status_code=400, detail=f"Spotify Auth Error: {error}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")
    signed_state = request.cookies.get(OAUTH_STATE_COOKIE)
    if not signed_state:
        raise HTTPException(status_code=400, detail="Missing oauth_state cookie")
    try:
        original_state = _serializer().loads(signed_state)
    except BadSignature:
        raise HTTPException(status_code=400, detail="Invalid oauth_state signature")
    if not secrets.compare_digest(original_state, state):
        raise HTTPException(status_code=400, detail="State mismatch")
    try:
        tokens = await spotify_adapter.exchange_code_for_tokens(code)
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        expires_in = tokens["expires_in"]

        profile = await spotify_adapter.get_user_profile(access_token)
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Spotify request failed ({e.response.status_code}): {e.response.text}",
        )
    spotify_id = profile["id"]
    display_name = profile.get("display_name") or spotify_id
    images = profile.get("images") or []
    avatar_url = images[0]["url"] if images else None

    now = datetime.now(timezone.utc)
    token_expires_at = now + timedelta(seconds=expires_in)

    user = session.get(User, (Provider.SPOTIFY, spotify_id))
    if user is None:
        user = User(
            provider=Provider.SPOTIFY,
            provider_user_id=spotify_id,
            display_name=display_name,
            avatar_url=avatar_url,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
        )
        session.add(user)
    else:
        user.display_name = display_name
        user.avatar_url = avatar_url
        user.access_token = access_token
        user.refresh_token = refresh_token  # callback SEMPRE traz novo refresh_token
        user.token_expires_at = token_expires_at
        user.updated_at = now
    session.commit()

    redirect = RedirectResponse(url=settings.FRONTEND_URL, status_code=303)
    redirect.delete_cookie(OAUTH_STATE_COOKIE, **_cookie_security_kwargs())
    redirect.set_cookie(
        key=SESSION_COOKIE,
        value=_session_serializer().dumps({"provider": "spotify", "id": spotify_id}),
        max_age=SESSION_COOKIE_MAX_AGE,
        httponly=True,
        **_cookie_security_kwargs(),
    )
    return redirect


@router.get("/me", response_model=MeResponse)
async def get_me(
    request: Request,
    session: Session = Depends(get_session),
):
    signed = request.cookies.get(SESSION_COOKIE)
    if not signed:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        session_data = _session_serializer().loads(signed)
        provider = session_data.get("provider")
        provider_user_id = session_data.get("id")
    except BadSignature:
        resp = JSONResponse(status_code=401, content={"detail": "Invalid session"})
        resp.delete_cookie(SESSION_COOKIE, **_cookie_security_kwargs())
        return resp

    user = session.get(User, (provider, provider_user_id))
    if user is None:
        resp = JSONResponse(status_code=401, content={"detail": "User not found"})
        resp.delete_cookie(SESSION_COOKIE, **_cookie_security_kwargs())
        return resp

    return MeResponse(
        provider=provider,
        provider_user_id=user.provider_user_id,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
    )


@router.post("/logout", status_code=204)
async def logout():
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, **_cookie_security_kwargs())
    return response

@router.get("/lastfm")
async def lastfm_login():
    qs = urlencode({
        "api_key": settings.LASTFM_API_KEY,
        "cb": settings.LASTFM_REDIRECT_URI,
    })
    return RedirectResponse(f"{LASTFM_AUTH_URL}?{qs}", status_code=302)


@router.get("/lastfm/callback")
async def lastfm_callback(token: str, db=Depends(get_session)):
    try:
        data = await lastfm_adapter.exchange_token_for_session(token)
    except lastfm_adapter.LastfmAPIError as e:
        raise HTTPException(status_code=400, detail=f"Last.fm error {e.code}: {e.message}")

    session = data["session"]
    session_key = session["key"]
    username = session["name"]

    try:
        user = await lastfm_for_user.upsert_user_from_session(db, session_key, username)
    except lastfm_adapter.LastfmAPIError as e:
        raise HTTPException(status_code=502, detail=f"Last.fm error {e.code}: {e.message}")

    response = RedirectResponse(settings.FRONTEND_URL, status_code=302)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=_session_serializer().dumps({"provider": "lastfm", "id": username}),
        max_age=SESSION_COOKIE_MAX_AGE,
        httponly=True,
        **_cookie_security_kwargs(),
    )
    return response