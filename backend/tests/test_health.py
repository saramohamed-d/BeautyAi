"""
Integration tests for Sprint 0 endpoints.

These tests hit the real /health endpoint, which in turn pings Postgres
and Redis. This means they require the docker-compose services to be
running (see README "Run tests" section) — that's intentional for
Sprint 0: we want to confirm the whole stack (API + DB + cache) is wired
together correctly, not just that individual functions work in isolation.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_returns_service_info(client: AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "running"
    assert "service" in body


@pytest.mark.asyncio
async def test_health_endpoint_reports_all_components(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()

    assert body["status"] in {"ok", "degraded"}
    component_names = {c["name"] for c in body["components"]}
    assert component_names == {"postgres", "redis"}


@pytest.mark.asyncio
async def test_health_endpoint_shape_matches_schema(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    body = response.json()

    for component in body["components"]:
        assert component["status"] in {"ok", "error"}
        assert "name" in component
