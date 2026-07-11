"""Central configuration — loaded once at startup."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------------------------
# Paths (absolute, resolved from this file's location)
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent

COOKIES_DIR = ROOT_DIR / "cookies"
COOKIES_FILE = COOKIES_DIR / "account.json"
STOCKTWITS_COOKIES_FILE = COOKIES_DIR / "stocktwits.json"

LOGS_DIR = ROOT_DIR / "logs"
EXPORTS_DIR = ROOT_DIR / "exports"
CACHE_DIR = ROOT_DIR / "cache"
ASSETS_DIR = ROOT_DIR / "assets"

for _d in (COOKIES_DIR, LOGS_DIR, EXPORTS_DIR, CACHE_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Settings model
# ---------------------------------------------------------------------------
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Credentials (optional — user may log in via UI)
    x_username: str = ""
    x_email: str = ""
    x_password: str = ""

    # App
    app_language: str = "es"
    app_theme: Literal["dark", "light"] = "dark"

    # Database
    database_url: str = f"sqlite:///{ROOT_DIR}/twitter_studio.db"

    # Cache
    cache_ttl: int = Field(default=300, ge=30)

    # Monitor
    monitor_interval: int = Field(default=60, ge=10)

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Search defaults
    default_search_limit: int = Field(default=50, ge=1, le=500)


# Singleton
settings = Settings()
