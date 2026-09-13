"""
Test data factories.

Design decision: these build prerequisite resources (a patient, a doctor,
a clinic...) THROUGH the real HTTP API (using the same AsyncClient a test
uses), not by inserting ORM rows directly. This means every test is also,
incidentally, continuously verifying that resource creation actually
works end-to-end — the same reason Sprint 1 chose to seed via the ORM
rather than raw SQL, applied one layer up.
"""

import uuid

from httpx import AsyncClient


def unique_phone() -> str:
    return f"+2010{uuid.uuid4().int % 10**8:08d}"


def unique_slug(prefix: str = "proc") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def make_patient(client: AsyncClient, **overrides) -> dict:
    payload = {"full_name": "Test Patient", "phone": unique_phone()}
    payload.update(overrides)
    resp = await client.post("/api/v1/patients", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def make_doctor(client: AsyncClient, **overrides) -> dict:
    payload = {"full_name": "Test Doctor", "specialty": "Dermatology"}
    payload.update(overrides)
    resp = await client.post("/api/v1/doctors", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def make_clinic(client: AsyncClient, **overrides) -> dict:
    payload = {"name": "Test Clinic", "city": "Cairo"}
    payload.update(overrides)
    resp = await client.post("/api/v1/clinics", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def make_procedure(client: AsyncClient, **overrides) -> dict:
    payload = {"name": "Test Procedure", "slug": unique_slug(), "category": "injectable"}
    payload.update(overrides)
    resp = await client.post("/api/v1/procedures", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def make_availability(client: AsyncClient, doctor_id: str, clinic_id: str, **overrides) -> dict:
    from datetime import datetime, timedelta, timezone

    start = datetime.now(timezone.utc) + timedelta(days=1)
    payload = {
        "doctor_id": doctor_id,
        "clinic_id": clinic_id,
        "start_time": start.isoformat(),
        "end_time": (start + timedelta(minutes=30)).isoformat(),
    }
    payload.update(overrides)
    resp = await client.post("/api/v1/availability", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def make_conversation(client: AsyncClient, **overrides) -> dict:
    payload = {"channel": "web", "language": "ar"}
    payload.update(overrides)
    resp = await client.post("/api/v1/conversations", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()
