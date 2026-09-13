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

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
