from datetime import datetime, timezone
from sqlmodel import Session, select
from app.models import User
from app import lastfm_adapter


async def upsert_user_from_session(
    db: Session,
    session_key: str,
    username: str,
) -> User:
    info = await lastfm_adapter.get_user_info(username)
    user_obj = info.get("user", {})
    display_name = user_obj.get("realname") or username
    images = user_obj.get("image", [])
    avatar_url = next(
        (img["#text"] for img in images if img.get("size") == "extralarge" and img.get("#text")),
        None,
    )

    existing = db.exec(
        select(User).where(
            User.provider == "lastfm",
            User.provider_user_id == username,
        )
    ).first()

    now = datetime.now(timezone.utc)
    if existing:
        existing.lastfm_session_key = session_key
        existing.display_name = display_name
        existing.avatar_url = avatar_url
        existing.updated_at = now
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    user = User(
        provider="lastfm",
        provider_user_id=username,
        display_name=display_name,
        avatar_url=avatar_url,
        lastfm_session_key=session_key,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


async def fetch_recent_filtered(
    username: str,
    album_name: str,
    limit: int = 5,
) -> list[dict]:
    """Pega scrobbles recentes e filtra por álbum (case-insensitive)."""
    data = await lastfm_adapter.get_recent_tracks(username, limit=200)
    tracks = data.get("recenttracks", {}).get("track", [])
    target = album_name.strip().casefold()
    filtered = [
        t for t in tracks
        if t.get("album", {}).get("#text", "").strip().casefold() == target
    ]
    return filtered[:limit]