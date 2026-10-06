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

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "change-me-in-env"


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

    # --- AI (Sprint 7) ---
    # "demo" is a deterministic, offline stand-in for local development and
    # tests (no API key, no cost). Staging/production must use a real model.
    # "ollama" runs a local model (free, no token budget) — local development only.
    ai_provider: Literal["openai", "ollama", "demo"] = "demo"
    openai_api_key: str | None = None
    # No default on purpose: pick and pin the model explicitly per environment.
    openai_model: str | None = None
    # Embeddings for the knowledge search (Sprint 8). Same provider switch as
    # the chat; with "openai" the model must be named explicitly (e.g.
    # text-embedding-3-small). Vectors are always 1536-dimensional.
    openai_embedding_model: str | None = None
    # Ollama: where it listens and which pulled model to use (`ollama list`).
    # From inside Docker use http://host.docker.internal:11434.
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    ollama_num_ctx: int = 8192
    ai_timeout_seconds: float = 30.0
    # Where data/knowledge/ lives (Markdown articles). Default: the repo's data folder.
    knowledge_dir: str | None = None
    # Cost/abuse limits for the chat.
    chat_max_message_chars: int = 2000
    chat_messages_per_hour: int = 30
    chat_history_messages: int = 20

    # --- Auth ---
    jwt_secret_key: str = DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    refresh_cookie_name: str = "beautyai_refresh"

    # --- Uploads (doctor verification documents, Sprint 12) ---
    # Where uploaded files are written. Relative paths are resolved from the
    # backend directory; keep it outside the repo in production.
    upload_dir: str = "var/uploads"
    max_upload_mb: int = 10

    # --- Booking ---
    # How long a slot stays reserved for a patient on the payment step.
    slot_hold_minutes: int = 10
    # Clinics' local time zone: "tomorrow at 5 PM" and time-of-day filters mean this zone.
    clinic_timezone: str = "Africa/Cairo"

    # --- Rate limiting (Sprint 17; docs/security.md) ---
    # Off only for the test suite, which makes hundreds of sign-ups and
    # logins from one address on purpose.
    rate_limit_enabled: bool = True

    # --- Notifications (Sprint 15; docs/notifications.md) ---
    # "demo" logs messages instead of sending them (local/test).
    notification_provider: Literal["demo", "live"] = "demo"
    # Email, over any SMTP server.
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_use_tls: bool = True
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "BeautyAI <no-reply@beautyai.example.com>"
    # SMS and WhatsApp, through Twilio.
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_sms_from: str | None = None
    twilio_whatsapp_from: str | None = None
    # How long before an appointment the reminder goes out, and how long
    # after it the aftercare message does.
    reminder_hours_before: int = 24
    aftercare_hours_after: int = 24

    # --- Payments (Sprint 11; docs/payments.md) ---
    # "demo" = a fake checkout page served by this API, for local development
    # and tests. Staging/production must use "paymob".
    payment_provider: Literal["paymob", "demo"] = "demo"
    # How long the slot stays held while the patient is on the gateway's checkout.
    payment_window_minutes: int = 15
    # Public URLs: the gateway calls the API's webhook and sends the patient back to the app.
    public_api_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    paymob_base_url: str = "https://accept.paymob.com"
    paymob_secret_key: str | None = None
    paymob_public_key: str | None = None
    paymob_hmac_secret: str | None = None
    # Integration IDs from the Paymob dashboard; a method is offered only if its ID is set.
    paymob_card_integration_id: int | None = None
    paymob_wallet_integration_id: int | None = None

    @field_validator("paymob_card_integration_id", "paymob_wallet_integration_id", mode="before")
    @classmethod
    def _blank_is_unset(cls, value):
        # .env.example leaves these blank; blank means "method not offered".
        return None if value == "" else value

    @property
    def cookie_secure(self) -> bool:
        """Refresh cookie is HTTPS-only everywhere except local dev and tests."""
        return self.app_env in ("staging", "production")

    @model_validator(mode="after")
    def _require_real_secret_outside_dev(self) -> "Settings":
        # Fail fast: a guessable signing key lets anyone mint admin tokens.
        if self.app_env in ("staging", "production") and (
            self.jwt_secret_key == DEV_JWT_SECRET or len(self.jwt_secret_key) < 32
        ):
            raise ValueError("JWT_SECRET_KEY must be set to a random value of at least 32 characters")
        if self.app_env in ("staging", "production") and self.ai_provider != "openai":
            raise ValueError("AI_PROVIDER must be 'openai' outside local development")
        if self.app_env in ("staging", "production") and self.notification_provider != "live":
            raise ValueError("NOTIFICATION_PROVIDER must be 'live' outside local development")
        if self.notification_provider == "live" and not self.smtp_username:
            raise ValueError("NOTIFICATION_PROVIDER=live needs SMTP credentials (SMTP_USERNAME, SMTP_PASSWORD)")
        if self.app_env in ("staging", "production") and self.payment_provider != "paymob":
            raise ValueError("PAYMENT_PROVIDER must be 'paymob' outside local development")
        if self.payment_provider == "paymob" and not (
            self.paymob_secret_key and self.paymob_public_key and self.paymob_hmac_secret
            and (self.paymob_card_integration_id or self.paymob_wallet_integration_id)
        ):
            raise ValueError(
                "PAYMENT_PROVIDER=paymob needs PAYMOB_SECRET_KEY, PAYMOB_PUBLIC_KEY, PAYMOB_HMAC_SECRET "
                "and at least one integration ID"
            )
        if self.ai_provider == "openai" and not (self.openai_api_key and self.openai_model and self.openai_embedding_model):
            raise ValueError("AI_PROVIDER=openai needs OPENAI_API_KEY, OPENAI_MODEL and OPENAI_EMBEDDING_MODEL")
        return self


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
