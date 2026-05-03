"""
openclaw/backend/config.py
Central settings object — loaded once, imported everywhere.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Mistral
    mistral_api_key: str = ""
    mistral_model: str = "mistral-small-latest"

    # Database
    database_url: str = "sqlite+aiosqlite:///./openclaw.db"

    # Security
    secret_key: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480
    token_encryption_key: str = ""

    # App
    app_name: str = "OpenClaw"
    app_env: str = "development"
    digest_recipients: str = ""

    # Google OAuth (optional)
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/oauth/callback"

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"

    @property
    def digest_recipient_list(self) -> list[str]:
        return [e.strip() for e in self.digest_recipients.split(",") if e.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
