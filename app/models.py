from datetime import datetime, timezone
from sqlmodel import SQLModel, Field

class User(SQLModel, table=True): 
    spotify_id: str = Field(primary_key=True)
    display_name: str
    avatar_url: str | None
    access_token: str
    refresh_token: str
    token_expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))