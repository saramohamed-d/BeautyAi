import uuid

import pytest
from httpx import AsyncClient

from tests.factories import make_doctor


@pytest.mark.asyncio
async def test_create_doctor_success(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/doctors", json={"full_name": "Dr. Test", "specialty": "Dermatology"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["verification_status"] == "pending"
    assert body["is_active"] is True


@pytest.mark.asyncio
async def test_create_doctor_invalid_years_experience_returns_422(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/doctors", json={"full_name": "Dr. Bad", "specialty": "Dermatology", "years_experience": -5}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_doctor_not_found_returns_404(client: AsyncClient) -> None:
    resp = await client.get(f"/api/v1/doctors/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_doctor_verification_status(client: AsyncClient) -> None:
    doctor = await make_doctor(client)
    resp = await client.patch(f"/api/v1/doctors/{doctor['id']}", json={"verification_status": "verified"})
    assert resp.status_code == 200
    assert resp.json()["verification_status"] == "verified"


@pytest.mark.asyncio
async def test_list_doctors_filter_by_specialty(client: AsyncClient) -> None:
    unique_specialty = f"Specialty-{uuid.uuid4().hex[:6]}"
    await make_doctor(client, specialty=unique_specialty)
    await make_doctor(client, specialty="Something Else")

    resp = await client.get(f"/api/v1/doctors?specialty={unique_specialty}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["specialty"] == unique_specialty


@pytest.mark.asyncio
async def test_list_doctors_filter_by_is_active(client: AsyncClient) -> None:
    doctor = await make_doctor(client)
    await client.patch(f"/api/v1/doctors/{doctor['id']}", json={"is_active": False})

    resp = await client.get(f"/api/v1/doctors?is_active=false")
    assert resp.status_code == 200
    ids = [d["id"] for d in resp.json()["items"]]
    assert doctor["id"] in ids
