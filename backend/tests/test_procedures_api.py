import uuid

import pytest
from httpx import AsyncClient

from tests.factories import make_procedure, unique_slug


@pytest.mark.asyncio
async def test_create_procedure_success(admin_client: AsyncClient) -> None:
    slug = unique_slug()
    resp = await admin_client.post("/api/v1/procedures", json={"name": "Botox", "slug": slug, "category": "injectable"})
    assert resp.status_code == 201
    assert resp.json()["slug"] == slug


@pytest.mark.asyncio
async def test_create_procedure_duplicate_slug_returns_409(admin_client: AsyncClient) -> None:
    procedure = await make_procedure(admin_client)
    resp = await admin_client.post(
        "/api/v1/procedures", json={"name": "Other Name", "slug": procedure["slug"], "category": "laser"}
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_procedure_invalid_slug_format_returns_422(admin_client: AsyncClient) -> None:
    resp = await admin_client.post(
        "/api/v1/procedures", json={"name": "Bad Slug", "slug": "Not A Slug!", "category": "injectable"}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_procedure_not_found_returns_404(admin_client: AsyncClient) -> None:
    resp = await admin_client.get(f"/api/v1/procedures/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_procedure_success(admin_client: AsyncClient) -> None:
    procedure = await make_procedure(admin_client)
    resp = await admin_client.patch(f"/api/v1/procedures/{procedure['id']}", json={"typical_price_min": 1000})
    assert resp.status_code == 200
    assert float(resp.json()["typical_price_min"]) == 1000.0


@pytest.mark.asyncio
async def test_list_procedures_filter_by_category(admin_client: AsyncClient) -> None:
    unique_category = f"cat-{uuid.uuid4().hex[:6]}"
    await make_procedure(admin_client, category=unique_category)

    resp = await admin_client.get(f"/api/v1/procedures?category={unique_category}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["category"] == unique_category
