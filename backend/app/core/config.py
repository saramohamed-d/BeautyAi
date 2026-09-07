"""
Application configuration.

Design decision: use pydantic-settings (BaseSettings) as the ONE place
where environment variables are read and validated. Nothing else in the
codebase should call os.environ directly.

Why this matters:
- Fails fast at startup if required config is missing/malformed, instead
  of failing deep inside a request handler at 2am.
- Gives every value a type, a default (where safe), and a single source
  of truth that's easy to grep for.
- Keeps secrets out of code: values are injected via `.env` locally and
  via real environment variables in Docker/production.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App metadata ---
    app_name: str = "BeautyAI API"
    app_env: Literal["local", "test", "staging", "production"] = "local"
    api_v1_prefix: str = "/api/v1"
    debug: bool = True

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000

    # --- Database ---
    # Async URL is used by the FastAPI app at runtime.
    database_url: str = Field(
        default="postgresql+asyncpg://beautyai:beautyai@localhost:5432/beautyai"
    )
    # Sync URL is used by Alembic, which does not support async drivers.
    database_url_sync: str = Field(
        default="postgresql+psycopg2://beautyai:beautyai@localhost:5432/beautyai"
    )

    # --- Redis ---
    redis_url: str = Field(default="redis://localhost:6379/0")

    # --- CORS ---
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # --- Logging ---
    log_level: str = "INFO"
    log_json: bool = False  # human-readable locally, JSON in staging/prod

    # --- Secrets (populated in later sprints; declared now so .env.example
    # documents the full eventual shape of configuration) ---
    openai_api_key: str | None = None
    jwt_secret_key: str = "change-me-in-env"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings accessor.

    Why lru_cache: Settings() re-parses and re-validates environment
    variables every time it's constructed. Since config doesn't change
    during the process lifetime, we parse it once and reuse it. FastAPI's
    dependency injection (`Depends(get_settings)`) will just return the
    same cached object on every request, at near-zero cost.
    """
    return Settings()
