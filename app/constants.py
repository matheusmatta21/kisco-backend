# URLs base
SPOTIFY_AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"

# Last.fm
LASTFM_AUTH_URL = "http://www.last.fm/api/auth/"
LASTFM_API_BASE = "https://ws.audioscrobbler.com/2.0/"
LASTFM_RECENT_MAX_LIMIT = 200  # confirmar grafia exata como aparece no scrobble

# Scopes (separados por espaço)
SPOTIFY_SCOPES = "user-read-private user-read-recently-played"

# Limites da API
RECENTLY_PLAYED_MAX_LIMIT = 50

# Vida útil do access token (segundos) — pra cálculo de margem de refresh
ACCESS_TOKEN_TTL_SECONDS = 3600
TOKEN_REFRESH_MARGIN_SECONDS = 30

# Album alvo: Kiss All The Time. Disco, Occasionally. - Spotify
ALBUM_ID = "69BqE1V8Bzb9GCyeP1fFeR"

# Filtro por álbum (KISCO) Last.fm
ALBUM_NAME_LASTFM = "Kiss All The Time. Disco, Occasionally."
ARTIST_NAME_LASTFM = "Harry Styles"

# Quantidade de tracks por user no card
TRACKS_PER_USER = 5

# Scheduler do poller de plays (fase 10)
POLL_INTERVAL_SECONDS = 15 * 60  # 15 minutos
