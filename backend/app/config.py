"""Application settings, read from environment variables or a .env file.

Every setting can be overridden with an env var of the same name in upper case,
e.g. DATABASE_URL, YOUTUBE_API_KEY, COOKIE_SECURE, LOG_LEVEL.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Long Video Session Planner"
    api_prefix: str = "/api"

    # SQLite file by default so the app runs locally with no setup.
    # PostgreSQL: postgresql+psycopg://user:password@host:5432/planner
    database_url: str = f"sqlite:///{BACKEND_DIR / 'data' / 'planner.db'}"

    # Optional YouTube Data API v3 key. Kept on the server, never sent to browsers.
    youtube_api_key: str = ""

    session_days: int = 30
    cookie_name: str = "lvsp_session"
    # Set to true when the site is served over HTTPS (production).
    cookie_secure: bool = False

    log_level: str = "INFO"
    log_json: bool = True

    # Serve the frontend folder from FastAPI (handy locally; nginx can do it in production).
    serve_frontend: bool = True
    frontend_dir: Path = ROOT_DIR / "frontend"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
