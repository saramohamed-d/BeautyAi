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
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

# Design note: the test suite creates/tears down an event loop per test
# function (pytest-asyncio's default scope), but asyncpg connections are
# bound to the event loop they were created in. A pooled engine would try
# to reuse a connection from a prior test's (now-closed) loop and blow up
# with "attached to a different loop". NullPool sidesteps this by never
# holding a connection open between checkouts — acceptable for tests
# (low concurrency, correctness > pool efficiency); the app still gets a
# real connection pool in local/staging/production.
_engine_kwargs = {"echo": settings.debug and settings.app_env == "local", "future": True}
if settings.app_env == "test":
    _engine_kwargs["poolclass"] = NullPool
else:
    _engine_kwargs["pool_pre_ping"] = True

engine = create_async_engine(settings.database_url, **_engine_kwargs)

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
