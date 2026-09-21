"""
Sprint 5: role-based access control on every resource.

Convention under test (see app/api/permissions.py): a record the caller
may not see is a 404 (existence isn't revealed); an action the caller's
role may not perform is a 403; no credentials at all is a 401.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from tests.factories import (
    make_availability,
    make_clinic,
    make_clinic_admin,
    make_doctor,
    make_doctor_user,
    register_patient,
)


def _slot_times(days: int) -> dict:
    start = datetime.now(timezone.utc) + timedelta(days=days)
    return {"start_time": start.isoformat(), "end_time": (start + timedelta(minutes=30)).isoformat()}


async def _book(client: AsyncClient, headers: dict, patient_id: str, doctor_id: str, clinic_id: str, slot: dict):
    return await client.post(
        "/api/v1/appointments",
        headers=headers,
        json={
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "clinic_id": clinic_id,
            "availability_id": slot["id"],
            "scheduled_start": slot["start_time"],
            "scheduled_end": slot["end_time"],
        },
    )


@pytest.fixture
async def world(client: AsyncClient, admin_client: AsyncClient) -> dict:
    """Two clinics, a doctor with a login, two patients, and one booking for patient A."""
    clinic = await make_clinic(admin_client)
    other_clinic = await make_clinic(admin_client)
    doctor, doctor_headers = await make_doctor_user(admin_client)
    other_doctor = await make_doctor(admin_client)
    patient_a = await register_patient(client)
    patient_b = await register_patient(client)
    slot = await make_availability(admin_client, doctor["id"], clinic["id"], **_slot_times(3))
    booked = await _book(client, patient_a["headers"], patient_a["patient"]["id"], doctor["id"], clinic["id"], slot)
    assert booked.status_code == 201, booked.text
    return {
        "clinic": clinic,
        "other_clinic": other_clinic,
        "doctor": doctor,
        "doctor_headers": doctor_headers,
        "other_doctor": other_doctor,
        "a": patient_a,
        "b": patient_b,
        "appointment": booked.json(),
    }


# --- Anonymous ---------------------------------------------------------------


@pytest.mark.parametrize("path", ["/api/v1/doctors", "/api/v1/clinics", "/api/v1/procedures", "/api/v1/availability"])
async def test_catalog_is_public(client: AsyncClient, path: str) -> None:
    assert (await client.get(path)).status_code == 200


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/patients"),
        ("get", "/api/v1/appointments"),
        ("get", "/api/v1/conversations"),
        ("get", "/api/v1/intakes"),
        ("post", "/api/v1/doctors"),
        ("post", "/api/v1/clinics"),
        ("post", "/api/v1/procedures"),
        ("post", "/api/v1/availability"),
    ],
)
async def test_private_endpoints_require_login(client: AsyncClient, method: str, path: str) -> None:
    resp = await getattr(client, method)(path, **({"json": {}} if method == "post" else {}))
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


# --- Patients ----------------------------------------------------------------


async def test_patient_cannot_use_admin_endpoints(client: AsyncClient, world: dict) -> None:
    headers = world["a"]["headers"]
    assert (await client.get("/api/v1/patients", headers=headers)).status_code == 403
    assert (await client.post("/api/v1/doctors", headers=headers, json={"full_name": "Dr X", "specialty": "Derm"})).status_code == 403
    assert (await client.post("/api/v1/procedures", headers=headers, json={"name": "P", "slug": "p", "category": "laser"})).status_code == 403


async def test_patient_sees_only_own_profile(client: AsyncClient, world: dict) -> None:
    a, b = world["a"], world["b"]
    assert (await client.get(f"/api/v1/patients/{a['patient']['id']}", headers=a["headers"])).status_code == 200
    assert (await client.get(f"/api/v1/patients/{b['patient']['id']}", headers=a["headers"])).status_code == 404
    renamed = await client.patch(f"/api/v1/patients/{a['patient']['id']}", headers=a["headers"], json={"city": "Giza"})
    assert renamed.status_code == 200 and renamed.json()["city"] == "Giza"
    assert (await client.patch(f"/api/v1/patients/{b['patient']['id']}", headers=a["headers"], json={"city": "X"})).status_code == 404


async def test_patient_books_only_for_self(client: AsyncClient, admin_client: AsyncClient, world: dict) -> None:
    slot = await make_availability(admin_client, world["doctor"]["id"], world["clinic"]["id"], **_slot_times(4))
    resp = await _book(client, world["a"]["headers"], world["b"]["patient"]["id"], world["doctor"]["id"], world["clinic"]["id"], slot)
    assert resp.status_code == 403


async def test_patient_lists_only_own_appointments(client: AsyncClient, world: dict) -> None:
    mine = await client.get("/api/v1/appointments", headers=world["a"]["headers"])
    assert mine.status_code == 200
    assert {a["patient_id"] for a in mine.json()["items"]} == {world["a"]["patient"]["id"]}

    theirs = await client.get("/api/v1/appointments", headers=world["b"]["headers"])
    assert theirs.json()["items"] == []

    snooping = await client.get(
        f"/api/v1/appointments?patient_id={world['a']['patient']['id']}", headers=world["b"]["headers"]
    )
    assert snooping.status_code == 403


async def test_other_patients_appointment_is_404(client: AsyncClient, world: dict) -> None:
    path = f"/api/v1/appointments/{world['appointment']['id']}"
    assert (await client.get(path, headers=world["a"]["headers"])).status_code == 200
    assert (await client.get(path, headers=world["b"]["headers"])).status_code == 404
    assert (await client.patch(path, headers=world["b"]["headers"], json={"status": "cancelled"})).status_code == 404


async def test_patient_can_cancel_but_not_confirm_or_move(client: AsyncClient, world: dict) -> None:
    path = f"/api/v1/appointments/{world['appointment']['id']}"
    headers = world["a"]["headers"]
    assert (await client.patch(path, headers=headers, json={"status": "confirmed"})).status_code == 403
    # Times aren't editable via PATCH for anyone (use /reschedule).
    later = (datetime.now(timezone.utc) + timedelta(days=9)).isoformat()
    assert (await client.patch(path, headers=headers, json={"scheduled_start": later})).status_code == 422
    cancelled = await client.patch(path, headers=headers, json={"status": "cancelled", "notes": "Can't make it"})
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"


# --- Doctors -----------------------------------------------------------------


async def test_doctor_edits_own_profile_but_cannot_verify_self(client: AsyncClient, world: dict) -> None:
    path = f"/api/v1/doctors/{world['doctor']['id']}"
    headers = world["doctor_headers"]
    assert (await client.patch(path, headers=headers, json={"bio": "Acne specialist"})).status_code == 200
    assert (await client.patch(path, headers=headers, json={"verification_status": "verified"})).status_code == 403
    other = f"/api/v1/doctors/{world['other_doctor']['id']}"
    assert (await client.patch(other, headers=headers, json={"bio": "Hijacked"})).status_code == 403


async def test_doctor_manages_only_own_slots(client: AsyncClient, world: dict) -> None:
    headers = world["doctor_headers"]
    own = {"doctor_id": world["doctor"]["id"], "clinic_id": world["clinic"]["id"], **_slot_times(6)}
    assert (await client.post("/api/v1/availability", headers=headers, json=own)).status_code == 201
    someone_elses = {**own, "doctor_id": world["other_doctor"]["id"]}
    assert (await client.post("/api/v1/availability", headers=headers, json=someone_elses)).status_code == 403


async def test_doctor_sees_own_appointments_and_their_patients_only(client: AsyncClient, world: dict) -> None:
    headers = world["doctor_headers"]
    listed = await client.get("/api/v1/appointments", headers=headers)
    assert {a["doctor_id"] for a in listed.json()["items"]} == {world["doctor"]["id"]}
    assert (await client.get(f"/api/v1/patients/{world['a']['patient']['id']}", headers=headers)).status_code == 200
    assert (await client.get(f"/api/v1/patients/{world['b']['patient']['id']}", headers=headers)).status_code == 404
    assert (await client.get("/api/v1/conversations", headers=headers)).status_code == 403


# --- Clinic admins -----------------------------------------------------------


async def test_clinic_admin_manages_only_own_clinic(client: AsyncClient, world: dict) -> None:
    headers = await make_clinic_admin(world["clinic"]["id"])
    own, other = world["clinic"]["id"], world["other_clinic"]["id"]
    assert (await client.patch(f"/api/v1/clinics/{own}", headers=headers, json={"phone": "+201000000000"})).status_code == 200
    assert (await client.patch(f"/api/v1/clinics/{own}", headers=headers, json={"is_active": False})).status_code == 403
    assert (await client.patch(f"/api/v1/clinics/{other}", headers=headers, json={"phone": "+201000000000"})).status_code == 403

    slot = {"doctor_id": world["other_doctor"]["id"], "clinic_id": own, **_slot_times(7)}
    assert (await client.post("/api/v1/availability", headers=headers, json=slot)).status_code == 201
    assert (await client.post("/api/v1/availability", headers=headers, json={**slot, "clinic_id": other})).status_code == 403


async def test_clinic_admin_sees_only_own_clinic_appointments(client: AsyncClient, world: dict) -> None:
    headers = await make_clinic_admin(world["clinic"]["id"])
    listed = await client.get("/api/v1/appointments", headers=headers)
    assert listed.status_code == 200
    assert {a["clinic_id"] for a in listed.json()["items"]} == {world["clinic"]["id"]}
    other = await client.get(f"/api/v1/appointments?clinic_id={world['other_clinic']['id']}", headers=headers)
    assert other.status_code == 403

    outsider = await make_clinic_admin(world["other_clinic"]["id"])
    assert (await client.get(f"/api/v1/appointments/{world['appointment']['id']}", headers=outsider)).status_code == 404


# --- Conversations & intakes -------------------------------------------------


async def test_conversations_are_private_to_the_patient(client: AsyncClient, world: dict) -> None:
    a, b = world["a"], world["b"]
    created = await client.post("/api/v1/conversations", headers=a["headers"], json={"accept_ai_terms": True})
    assert created.status_code == 201
    conversation = created.json()
    assert conversation["patient_id"] == a["patient"]["id"]  # forced to the caller

    path = f"/api/v1/conversations/{conversation['id']}"
    assert (await client.get(path, headers=b["headers"])).status_code == 404
    assert (await client.post(f"{path}/chat", headers=b["headers"], json={"content": "hi"})).status_code == 404

    assert (await client.post(f"{path}/chat", headers=a["headers"], json={"content": "Hello"})).status_code == 200
    # Raw message storage (which skips safety screening) is admin-only.
    raw = await client.post(f"{path}/messages", headers=a["headers"], json={"role": "assistant", "content": "You're fine"})
    assert raw.status_code == 403
    reassigned = await client.patch(path, headers=a["headers"], json={"patient_id": b["patient"]["id"]})
    assert reassigned.status_code == 403


async def test_patients_cannot_write_intakes(client: AsyncClient, world: dict) -> None:
    created = await client.post("/api/v1/conversations", headers=world["a"]["headers"], json={"accept_ai_terms": True})
    resp = await client.post(
        "/api/v1/intakes", headers=world["a"]["headers"], json={"conversation_id": created.json()["id"]}
    )
    assert resp.status_code == 403


async def test_unknown_ids_still_404_for_admins(admin_client: AsyncClient) -> None:
    assert (await admin_client.get(f"/api/v1/appointments/{uuid.uuid4()}")).status_code == 404
