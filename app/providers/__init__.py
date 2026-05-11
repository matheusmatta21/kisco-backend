from app.providers.base import MusicProvider
from app.providers.lastfm import LastfmProvider
from app.providers.spotify import SpotifyProvider

PROVIDERS: dict[str, MusicProvider] = {
    "spotify": SpotifyProvider(),
    "lastfm": LastfmProvider(),
}

__all__ = ["MusicProvider", "PROVIDERS"]
