from datetime import datetime, timezone

from app.constants import ALBUM_ID, ALBUM_NAME_LASTFM, ARTIST_NAME_LASTFM
from app.models import Play, User


def _make_track_key(first_artist: str, track_name: str) -> str:
    return f"{first_artist.strip().casefold()}::{track_name.strip().casefold()}"


# --- Spotify ---------------------------------------------------------------


def is_target_spotify_album(item: dict) -> bool:
    track = item.get("track") or {}
    album = track.get("album") or {}
    return album.get("id") == ALBUM_ID


def normalize_spotify_play(item: dict, user: User) -> Play:
    track = item["track"]
    artists = [a["name"] for a in track.get("artists", []) if a.get("name")]
    first_artist = artists[0] if artists else ""
    images = track["album"].get("images") or []
    return Play(
        provider=user.provider,
        provider_user_id=user.provider_user_id,
        played_at=_parse_spotify_played_at(item["played_at"]),
        track_key=_make_track_key(first_artist, track["name"]),
        track_name=track["name"],
        artists=", ".join(artists),
        album_name=track["album"]["name"],
        image_url=images[0]["url"] if images else None,
    )


def _parse_spotify_played_at(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# --- Last.fm ---------------------------------------------------------------


def is_target_lastfm_track(track: dict) -> bool:
    album = (track.get("album") or {}).get("#text", "").strip().casefold()
    artist = (track.get("artist") or {}).get("#text", "").strip().casefold()
    return (
        album == ALBUM_NAME_LASTFM.strip().casefold()
        and artist == ARTIST_NAME_LASTFM.strip().casefold()
    )


def normalize_lastfm_play(track: dict, user: User) -> Play | None:
    if (track.get("@attr") or {}).get("nowplaying") == "true":
        return None

    uts = (track.get("date") or {}).get("uts")
    if not uts:
        return None

    artist_text = (track.get("artist") or {}).get("#text", "")
    images = track.get("image") or []
    image_url = next(
        (
            img["#text"]
            for img in images
            if img.get("size") == "extralarge" and img.get("#text")
        ),
        None,
    )
    return Play(
        provider=user.provider,
        provider_user_id=user.provider_user_id,
        played_at=datetime.fromtimestamp(int(uts), tz=timezone.utc),
        track_key=_make_track_key(artist_text, track.get("name", "")),
        track_name=track.get("name", ""),
        artists=artist_text,
        album_name=(track.get("album") or {}).get("#text", ""),
        image_url=image_url,
    )
