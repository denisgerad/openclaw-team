"""
openclaw/backend/config.py
Central settings object — loaded once, imported everywhere.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

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

    # ── Network / Upload (remote developer access) ────────────────────────────
    # Comma-separated CORS origins — add every machine that will access the API.
    #   ALLOWED_ORIGINS=http://192.168.1.50:3000,http://my-dev-box:3000
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"

    # Maximum upload file size in MB (enforced server-side)
    max_upload_mb: int = 200

    # Public server URL shown in CLI output and upload confirmations.
    # Set to the LAN IP or domain where OpenClaw is reachable from dev machines.
    #   SERVER_URL=http://192.168.1.50:8000
    server_url: str = "http://localhost:8000"

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

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
