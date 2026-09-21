import uuid

import pytest
from httpx import AsyncClient

from tests.factories import make_availability, make_clinic, make_doctor, make_patient


async def _booking_payload(admin_client: AsyncClient, **extra) -> dict:
    patient = await make_patient(admin_client)
    doctor = await make_doctor(admin_client)
    clinic = await make_clinic(admin_client)
    slot = await make_availability(admin_client, doctor["id"], clinic["id"])
    payload = {
        "patient_id": patient["id"],
        "doctor_id": doctor["id"],
        "clinic_id": clinic["id"],
        "availability_id": slot["id"],
        "scheduled_start": slot["start_time"],
        "scheduled_end": slot["end_time"],
    }
    payload.update(extra)
    return payload


@pytest.mark.asyncio
async def test_create_appointment_success(admin_client: AsyncClient) -> None:
    payload = await _booking_payload(admin_client)
    resp = await admin_client.post("/api/v1/appointments", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "pending"

    # The slot itself must now be marked booked — data consistency
    # guaranteed by the same transaction, not eventual/async.
    slot_resp = await admin_client.get(f"/api/v1/availability/{payload['availability_id']}")
    assert slot_resp.json()["is_booked"] is True


@pytest.mark.asyncio
async def test_create_appointment_on_already_booked_slot_returns_409(admin_client: AsyncClient) -> None:
    payload = await _booking_payload(admin_client)
    first = await admin_client.post("/api/v1/appointments", json=payload)
    assert first.status_code == 201

    # Same slot, different (new) patient — must fail on the SLOT, not the patient.
    other_patient = await make_patient(admin_client)
    second_payload = dict(payload, patient_id=other_patient["id"])
    second = await admin_client.post("/api/v1/appointments", json=second_payload)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_create_appointment_duplicate_idempotency_key_returns_409(admin_client: AsyncClient) -> None:
    key = str(uuid.uuid4())
    payload1 = await _booking_payload(admin_client, idempotency_key=key)
    resp1 = await admin_client.post("/api/v1/appointments", json=payload1)
    assert resp1.status_code == 201

    payload2 = await _booking_payload(admin_client, idempotency_key=key)
    resp2 = await admin_client.post("/api/v1/appointments", json=payload2)
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_create_appointment_nonexistent_patient_returns_404(admin_client: AsyncClient) -> None:
    payload = await _booking_payload(admin_client)
    payload["patient_id"] = str(uuid.uuid4())
    resp = await admin_client.post("/api/v1/appointments", json=payload)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_appointment_invalid_times_returns_422(admin_client: AsyncClient) -> None:
    payload = await _booking_payload(admin_client)
    payload["scheduled_end"] = payload["scheduled_start"]
    resp = await admin_client.post("/api/v1/appointments", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_appointment_status_to_cancelled_frees_slot(admin_client: AsyncClient) -> None:
    payload = await _booking_payload(admin_client)
    created = (await admin_client.post("/api/v1/appointments", json=payload)).json()

    resp = await admin_client.patch(f"/api/v1/appointments/{created['id']}", json={"status": "cancelled"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"

    slot_resp = await admin_client.get(f"/api/v1/availability/{payload['availability_id']}")
    assert slot_resp.json()["is_booked"] is False


@pytest.mark.asyncio
async def test_list_appointments_filter_by_status(admin_client: AsyncClient) -> None:
    payload = await _booking_payload(admin_client)
    created = (await admin_client.post("/api/v1/appointments", json=payload)).json()

    resp = await admin_client.get(f"/api/v1/appointments?status=pending&patient_id={payload['patient_id']}")
    assert resp.status_code == 200
    ids = [a["id"] for a in resp.json()["items"]]
    assert created["id"] in ids
    cancelled = await admin_client.get(f"/api/v1/appointments?status=cancelled&patient_id={payload['patient_id']}")
    assert cancelled.json()["items"] == []
