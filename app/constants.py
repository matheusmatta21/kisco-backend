# URLs base
SPOTIFY_AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"

# Scopes (separados por espaço)
SPOTIFY_SCOPES = "user-read-private user-read-recently-played"

# Limites da API
RECENTLY_PLAYED_MAX_LIMIT = 50

# Vida útil do access token (segundos) — pra cálculo de margem de refresh
ACCESS_TOKEN_TTL_SECONDS = 3600
TOKEN_REFRESH_MARGIN_SECONDS = 30

# Album alvo: "Kiss All The Time" (Disco Ocasionally)
ALBUM_ID = "69BqE1V8Bzb9GCyeP1fFeR"

# Quantidade de tracks por user no card
TRACKS_PER_USER = 5
