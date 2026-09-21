"""
Production readiness check (Sprint 17; docs/deployment.md).

    python -m app.scripts.preflight

Answers one question before a deploy: is this configuration safe to serve
real patients? It checks what a person would otherwise have to remember —
secrets, providers, debug flags, CORS, TLS-only cookies, and whether the
database is migrated — and exits non-zero if anything is wrong.

It reads configuration and the database only; it changes nothing.
"""

import asyncio
import sys

from pydantic import ValidationError

from app.core.config import DEV_JWT_SECRET, get_settings

OK, WARN, FAIL = "ok", "warn", "fail"


def _config_checks(settings) -> list[tuple[str, str, str]]:
    production = settings.app_env in ("staging", "production")
    checks: list[tuple[str, str, str]] = []

    def add(name: str, condition: bool, detail: str, *, level: str = FAIL) -> None:
        checks.append((name, OK if condition else level, "" if condition else detail))

    add("APP_ENV", settings.app_env in ("local", "test", "staging", "production"), f"unknown: {settings.app_env}")
    add(
        "JWT secret",
        not production or (settings.jwt_secret_key != DEV_JWT_SECRET and len(settings.jwt_secret_key) >= 32),
        "set JWT_SECRET_KEY to a random value of 32+ characters",
    )
    add("Debug off", not (production and settings.debug), "DEBUG must be false outside development")
    add("AI provider", not production or settings.ai_provider == "openai", "AI_PROVIDER must be 'openai'")
    add("Payments", not production or settings.payment_provider == "paymob", "PAYMENT_PROVIDER must be 'paymob'")
    add(
        "Notifications",
        not production or settings.notification_provider == "live",
        "NOTIFICATION_PROVIDER must be 'live'",
    )
    add("Secure cookies", not production or settings.cookie_secure, "refresh cookie must be HTTPS-only")
    add(
        "CORS",
        bool(settings.cors_origins) and not (production and any("*" in origin for origin in settings.cors_origins)),
        "CORS_ORIGINS must list the real frontend origins, no wildcard",
    )
    add(
        "Public URLs",
        not production or (settings.public_api_url.startswith("https://") and settings.frontend_url.startswith("https://")),
        "PUBLIC_API_URL and FRONTEND_URL must be https:// (payment webhooks and reset links use them)",
    )
    add(
        "Uploads",
        not production or not settings.upload_dir.startswith("var/"),
        "UPLOAD_DIR should be a mounted volume outside the app directory",
        level=WARN,
    )
    return checks


async def _database_checks() -> list[tuple[str, str, str]]:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    from sqlalchemy import text

    # Imported here: it reads the settings at import time, which must have
    # been validated first.
    from app.db.session import AsyncSessionLocal

    checks = []
    try:
        async with AsyncSessionLocal() as db:
            current = (await db.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            head = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
            checks.append(
                ("Migrations", OK if current == head else FAIL, "" if current == head else f"at {current}, head is {head}")
            )
            extensions = (await db.execute(text("SELECT extname FROM pg_extension"))).scalars().all()
            checks.append(
                ("pgvector", OK if "vector" in extensions else FAIL, "" if "vector" in extensions else "extension missing")
            )
            approved = (
                await db.execute(text("SELECT count(*) FROM knowledge_documents WHERE status = 'approved'"))
            ).scalar()
            checks.append(
                ("Knowledge", OK if approved else WARN, "" if approved else "no approved articles: the chat has nothing to cite")
            )
    except Exception as exc:
        checks.append(("Database", FAIL, f"{type(exc).__name__}: {exc}"))
    return checks


async def run() -> int:
    try:
        settings = get_settings()
    except ValidationError as exc:
        # The app refuses to start on a bad configuration; say why instead
        # of showing a stack trace.
        print("Preflight — configuration rejected\n")
        for error in exc.errors():
            print(f"  ✗ {error.get('msg', error)}")
        print("\nNOT READY — fix the configuration above")
        return 1

    checks = _config_checks(settings) + await _database_checks()

    print(f"Preflight — {settings.app_name} ({settings.app_env})\n")
    symbols = {OK: "✓", WARN: "!", FAIL: "✗"}
    for name, level, detail in checks:
        print(f"  {symbols[level]} {name:<16} {detail}")

    failures = [name for name, level, _ in checks if level == FAIL]
    warnings = [name for name, level, _ in checks if level == WARN]
    print("")
    if failures:
        print(f"NOT READY — {len(failures)} problem(s): {', '.join(failures)}")
        return 1
    print("READY" + (f" — with warnings: {', '.join(warnings)}" if warnings else ""))
    return 0


def main() -> None:
    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
