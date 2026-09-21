import uuid

import pytest
from httpx import AsyncClient

from tests.factories import make_clinic


@pytest.mark.asyncio
async def test_create_clinic_success(admin_client: AsyncClient) -> None:
    resp = await admin_client.post("/api/v1/clinics", json={"name": "Test Clinic", "city": "Cairo"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["country"] == "Egypt"  # default applied
    assert body["is_active"] is True


@pytest.mark.asyncio
async def test_create_clinic_missing_required_field_returns_422(admin_client: AsyncClient) -> None:
    resp = await admin_client.post("/api/v1/clinics", json={"name": "No City"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_clinic_not_found_returns_404(admin_client: AsyncClient) -> None:
    resp = await admin_client.get(f"/api/v1/clinics/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_clinic_success(admin_client: AsyncClient) -> None:
    clinic = await make_clinic(admin_client)
    resp = await admin_client.patch(f"/api/v1/clinics/{clinic['id']}", json={"is_active": False})
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_list_clinics_filter_by_city(admin_client: AsyncClient) -> None:
    unique_city = f"City-{uuid.uuid4().hex[:6]}"
    await make_clinic(admin_client, city=unique_city)

    resp = await admin_client.get(f"/api/v1/clinics?city={unique_city}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["city"] == unique_city
