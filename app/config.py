from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    SPOTIFY_CLIENT_ID: str
    SPOTIFY_CLIENT_SECRET: str
    SPOTIFY_REDIRECT_URI: str

    LASTFM_API_KEY: str
    LASTFM_SHARED_SECRET: str
    LASTFM_REDIRECT_URI: str

    FRONTEND_URL: str
    # Default = SQLite local. Em prod, sobrescrever via .env com a connection
    # string do Supabase (postgresql+psycopg://...).
    DATABASE_URL: str = "sqlite:///./kisco.db"
    SESSION_SECRET: str



settings = Settings()
