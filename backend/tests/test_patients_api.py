import uuid

import pytest
from httpx import AsyncClient

from tests.factories import make_patient, unique_phone


@pytest.mark.asyncio
async def test_create_patient_success(client: AsyncClient) -> None:
    phone = unique_phone()
    resp = await client.post("/api/v1/patients", json={"full_name": "Nour Ahmed", "phone": phone})
    assert resp.status_code == 201
    body = resp.json()
    assert body["full_name"] == "Nour Ahmed"
    assert body["phone"] == phone
    assert body["preferred_language"] == "ar"
    assert "id" in body and "created_at" in body


@pytest.mark.asyncio
async def test_create_patient_duplicate_phone_returns_409(client: AsyncClient) -> None:
    patient = await make_patient(client)
    resp = await client.post("/api/v1/patients", json={"full_name": "Someone Else", "phone": patient["phone"]})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


@pytest.mark.asyncio
async def test_create_patient_invalid_phone_returns_422(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/patients", json={"full_name": "Bad Phone", "phone": "not-a-phone"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_patient_success(client: AsyncClient) -> None:
    patient = await make_patient(client)
    resp = await client.get(f"/api/v1/patients/{patient['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == patient["id"]


@pytest.mark.asyncio
async def test_get_patient_not_found_returns_404(client: AsyncClient) -> None:
    resp = await client.get(f"/api/v1/patients/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_update_patient_success(client: AsyncClient) -> None:
    patient = await make_patient(client)
    resp = await client.patch(f"/api/v1/patients/{patient['id']}", json={"full_name": "Updated Name"})
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Updated Name"
    # Untouched fields survive a partial update.
    assert resp.json()["phone"] == patient["phone"]


@pytest.mark.asyncio
async def test_update_patient_not_found_returns_404(client: AsyncClient) -> None:
    resp = await client.patch(f"/api/v1/patients/{uuid.uuid4()}", json={"full_name": "Valid Name"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_patients_pagination(client: AsyncClient) -> None:
    for _ in range(3):
        await make_patient(client)

    resp = await client.get("/api/v1/patients?page=1&page_size=2")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total"] >= 3
    assert body["pages"] >= 2


@pytest.mark.asyncio
async def test_list_patients_search_by_name(client: AsyncClient) -> None:
    unique_name = f"Zzyxx-{uuid.uuid4().hex[:6]}"
    await make_patient(client, full_name=unique_name)

    resp = await client.get(f"/api/v1/patients?search={unique_name}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["full_name"] == unique_name
