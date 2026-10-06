"""
Shared pytest fixtures.

Design decision: use httpx.AsyncClient with ASGITransport against the
real FastAPI `app` object (in-process), rather than spinning up a live
uvicorn server for tests.

Why: in-process ASGI testing is fast (no real sockets/ports), deterministic,
and works the same in CI as locally. It exercises the actual FastAPI
app — middleware, dependency overrides, routing — so it's a genuine
integration test of the wiring in main.py, not just unit tests of
individual functions.
"""

import os

# Must be set before `app.db.session` is imported anywhere (including
# transitively via `app.main`), since it decides the DB connection pool
# strategy (see app/db/session.py's NullPool note).

os.environ["APP_ENV"] = "test"
# The suite signs hundreds of patients up from one address; the limiter is
# exercised deliberately in tests/test_account_security.py instead.
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
# Tests use the offline demo AI, even when a local .env picks Ollama or OpenAI.
os.environ["AI_PROVIDER"] = "demo"

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.enums import UserRole
from tests.factories import bearer, create_user


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Anonymous client — no Authorization header."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def admin_client() -> AsyncGenerator[AsyncClient, None]:
    """Client authenticated as a fresh platform admin. Used to set up data and test admin paths."""
    admin = await create_user(UserRole.PLATFORM_ADMIN)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=bearer(admin)) as ac:
        yield ac
