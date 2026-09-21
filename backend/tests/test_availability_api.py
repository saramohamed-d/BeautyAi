import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from tests.factories import make_availability, make_clinic, make_doctor


@pytest.mark.asyncio
async def test_create_availability_success(admin_client: AsyncClient) -> None:
    doctor = await make_doctor(admin_client)
    clinic = await make_clinic(admin_client)
    slot = await make_availability(admin_client, doctor["id"], clinic["id"])
    assert slot["is_booked"] is False
    assert slot["doctor_id"] == doctor["id"]


@pytest.mark.asyncio
async def test_create_availability_end_before_start_returns_422(admin_client: AsyncClient) -> None:
    doctor = await make_doctor(admin_client)
    clinic = await make_clinic(admin_client)
    start = datetime.now(timezone.utc) + timedelta(days=1)
    resp = await admin_client.post(
        "/api/v1/availability",
        json={
            "doctor_id": doctor["id"],
            "clinic_id": clinic["id"],
            "start_time": start.isoformat(),
            "end_time": (start - timedelta(minutes=30)).isoformat(),
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_availability_nonexistent_doctor_returns_404(admin_client: AsyncClient) -> None:
    clinic = await make_clinic(admin_client)
    start = datetime.now(timezone.utc) + timedelta(days=1)
    resp = await admin_client.post(
        "/api/v1/availability",
        json={
            "doctor_id": str(uuid.uuid4()),
            "clinic_id": clinic["id"],
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(minutes=30)).isoformat(),
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_availability_toggle_is_booked(admin_client: AsyncClient) -> None:
    doctor = await make_doctor(admin_client)
    clinic = await make_clinic(admin_client)
    slot = await make_availability(admin_client, doctor["id"], clinic["id"])

    resp = await admin_client.patch(f"/api/v1/availability/{slot['id']}", json={"is_booked": True})
    assert resp.status_code == 200
    assert resp.json()["is_booked"] is True


@pytest.mark.asyncio
async def test_list_availability_filter_by_doctor_and_booked(admin_client: AsyncClient) -> None:
    doctor = await make_doctor(admin_client)
    clinic = await make_clinic(admin_client)
    slot = await make_availability(admin_client, doctor["id"], clinic["id"])

    resp = await admin_client.get(f"/api/v1/availability?doctor_id={doctor['id']}&is_booked=false")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert all(item["doctor_id"] == doctor["id"] for item in body["items"])
    assert all(item["is_booked"] is False for item in body["items"])
    ids = [item["id"] for item in body["items"]]
    assert slot["id"] in ids
