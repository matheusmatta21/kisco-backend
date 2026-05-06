import httpx
import secrets
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeSerializer, BadSignature
from sqlmodel import Session
from urllib.parse import quote, urlencode

from app.config import settings
from app.constants import SPOTIFY_AUTHORIZE_URL, SPOTIFY_SCOPES
from app.db import get_session
from app.models import User
from app import spotify_adapter

router = APIRouter(tags=["auth"])

OAUTH_STATE_COOKIE = "oauth_state"
STATE_COOKIE_MAX_AGE = 600  # 10min


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(settings.SESSION_SECRET, salt="oauth-state")


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
    }
    authorize_url = f"{SPOTIFY_AUTHORIZE_URL}?{urlencode(params, quote_via=quote)}"

    redirect = RedirectResponse(url=authorize_url, status_code=303)
    redirect.set_cookie(
        key=OAUTH_STATE_COOKIE,
        value=signed_state,
        max_age=STATE_COOKIE_MAX_AGE,
        httponly=True,
        secure=False,  # True em produção (HTTPS). Em dev usamos http://127.0.0.1
        samesite="lax",  # "lax" permite redirect cross-site (Spotify → nosso callback)
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

    user = session.get(User, spotify_id)
    if user is None:
        user = User(
            spotify_id=spotify_id,
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
    redirect.delete_cookie(OAUTH_STATE_COOKIE)
    return redirect
