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
      FRONTEND_URL: str
      DATABASE_URL: str
      SESSION_SECRET: str


settings = Settings()