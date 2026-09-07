"""
Database engine and session management.

Design decision: async SQLAlchemy 2.0 engine, one engine per process,
sessions created per-request via a FastAPI dependency.

Why async:
- FastAPI is built on ASGI; using a sync driver (psycopg2) inside async
  route handlers would block the event loop under load. asyncpg + SQLAlchemy's
  async engine keep the whole request path non-blocking, which matters
  once we have concurrent chat/booking traffic.

Why a single engine, not one per request:
- Creating a new engine per request would create a new connection pool
  per request, exhausting Postgres connections almost immediately. The
  engine (and its pool) is created once at import time and reused; only
  *sessions* (logical transactions) are created per request.

Note on Alembic: Alembic's migration runner does not support async
drivers cleanly, so we keep a separate sync URL (settings.database_url_sync)
used only by alembic/env.py. The running application always uses the
async engine defined here.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug and settings.app_env == "local",
    pool_pre_ping=True,  # detects and discards dead connections before use
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """
    Shared declarative base for all ORM models.

    Sprint 1 will add models (patients, doctors, clinics, ...) that inherit
    from this Base, plus a mixin providing id/created_at/updated_at so we
    don't repeat those columns on every table.
    """


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a request-scoped DB session.

    Usage in a route:
        async def endpoint(db: AsyncSession = Depends(get_db)): ...

    The session is closed automatically at the end of the request via the
    `async with` block, regardless of whether the request succeeded or
    raised — preventing connection leaks.
    """
    async with AsyncSessionLocal() as session:
        yield session
