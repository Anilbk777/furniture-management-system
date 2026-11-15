from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    direct_database_url: str  # Neon non-pooled URL, used by Alembic
    debug: bool

    
    jwt_access_secret: SecretStr
    jwt_refresh_secret: SecretStr
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 3

    cookie_secure: bool = False  # use False for plain-http local dev
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    cookie_domain: str | None = None
    cors_origins: list[str] = []

settings = Settings()
