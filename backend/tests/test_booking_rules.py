"""Sprint 6: booking rules — slot reuse, concurrency, idempotency, holds, cancel/reschedule policy."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from httpx import AsyncClient
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.scheduling import Availability
from tests.factories import make_availability, make_clinic, make_doctor, make_patient, register_patient


def _at(hours: float) -> dict:
    start = datetime.now(timezone.utc) + timedelta(hours=hours)
    return {"start_time": start.isoformat(), "end_time": (start + timedelta(minutes=30)).isoformat()}


async def _world(admin_client: AsyncClient, cutoff_hours: int = 24, slot_in_hours: float = 72) -> dict:
    doctor = await make_doctor(admin_client)
    clinic = await make_clinic(admin_client, cancellation_cutoff_hours=cutoff_hours)
    slot = await make_availability(admin_client, doctor["id"], clinic["id"], **_at(slot_in_hours))
    return {"doctor": doctor, "clinic": clinic, "slot": slot}


def _payload(world: dict, patient_id: str, slot: dict | None = None, **extra) -> dict:
    slot = slot or world["slot"]
    return {
        "patient_id": patient_id,
        "doctor_id": slot["doctor_id"],
        "clinic_id": slot["clinic_id"],
        "availability_id": slot["id"],
        "scheduled_start": slot["start_time"],
        "scheduled_end": slot["end_time"],
        **extra,
    }


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


async def _slot(admin_client: AsyncClient, slot_id: str) -> dict:
    return (await admin_client.get(f"/api/v1/availability/{slot_id}")).json()


async def _expire_hold(slot_id: str) -> None:
    async with AsyncSessionLocal() as db:
        slot = await db.scalar(select(Availability).where(Availability.id == uuid.UUID(slot_id)))
        slot.held_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        await db.commit()


# --- The two Sprint 1-5 bugs ---------------------------------------------------


async def test_cancelled_slot_can_be_booked_again(admin_client: AsyncClient) -> None:
    world = await _world(admin_client)
    first = await admin_client.post("/api/v1/appointments", json=_payload(world, (await make_patient(admin_client))["id"]))
    assert first.status_code == 201
    cancel = await admin_client.patch(f"/api/v1/appointments/{first.json()['id']}", json={"status": "cancelled"})
    assert cancel.status_code == 200

    again = await admin_client.post("/api/v1/appointments", json=_payload(world, (await make_patient(admin_client))["id"]))
    assert again.status_code == 201, again.text
    # The cancelled booking keeps its link to the slot for history.
    history = await admin_client.get(f"/api/v1/appointments/{first.json()['id']}")
    assert history.json()["availability_id"] == world["slot"]["id"]


async def test_concurrent_bookings_for_one_slot_never_500(admin_client: AsyncClient) -> None:
    world = await _world(admin_client)
    patients = [await make_patient(admin_client) for _ in range(5)]
    responses = await asyncio.gather(
        *(admin_client.post("/api/v1/appointments", json=_payload(world, p["id"])) for p in patients)
    )
    assert sorted(r.status_code for r in responses) == [201, 409, 409, 409, 409], [r.text for r in responses]
    assert {r.json()["error"]["code"] for r in responses if r.status_code == 409} == {"slot_unavailable"}


# --- Booking correctness -------------------------------------------------------


async def test_idempotent_retry_returns_the_original_booking(admin_client: AsyncClient) -> None:
    world = await _world(admin_client)
    payload = _payload(world, (await make_patient(admin_client))["id"], idempotency_key=str(uuid.uuid4()))
    first, retry = [await admin_client.post("/api/v1/appointments", json=payload) for _ in range(2)]
    assert first.status_code == retry.status_code == 201
    assert first.json()["id"] == retry.json()["id"]


async def test_concurrent_retries_with_one_idempotency_key_create_one_booking(admin_client: AsyncClient) -> None:
    world = await _world(admin_client)
    payload = _payload(world, (await make_patient(admin_client))["id"], idempotency_key=str(uuid.uuid4()))
    responses = await asyncio.gather(*(admin_client.post("/api/v1/appointments", json=payload) for _ in range(4)))
    assert {r.status_code for r in responses} == {201}, [r.text for r in responses]
    assert len({r.json()["id"] for r in responses}) == 1


async def test_booking_times_always_come_from_the_slot(admin_client: AsyncClient) -> None:
    world = await _world(admin_client)
    fake = _at(500)
    payload = _payload(
        world, (await make_patient(admin_client))["id"], scheduled_start=fake["start_time"], scheduled_end=fake["end_time"]
    )
    booked = (await admin_client.post("/api/v1/appointments", json=payload)).json()
    assert _parse(booked["scheduled_start"]) == _parse(world["slot"]["start_time"])
    assert _parse(booked["scheduled_end"]) == _parse(world["slot"]["end_time"])


async def test_slot_must_match_doctor_and_clinic(admin_client: AsyncClient) -> None:
    world = await _world(admin_client)
    other_doctor = await make_doctor(admin_client)
    payload = _payload(world, (await make_patient(admin_client))["id"], doctor_id=other_doctor["id"])
    assert (await admin_client.post("/api/v1/appointments", json=payload)).status_code == 422


async def test_past_slot_cannot_be_booked(admin_client: AsyncClient) -> None:
    world = await _world(admin_client, slot_in_hours=-2)
    resp = await admin_client.post("/api/v1/appointments", json=_payload(world, (await make_patient(admin_client))["id"]))
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "slot_unavailable"


# --- Holds -----------------------------------------------------------------------


async def test_hold_reserves_the_slot_for_the_payer_only(client: AsyncClient, admin_client: AsyncClient) -> None:
    world = await _world(admin_client)
    slot_id = world["slot"]["id"]
    alice, bob = await register_patient(client), await register_patient(client)

    held = await client.post(f"/api/v1/availability/{slot_id}/hold", headers=alice["headers"])
    assert held.status_code == 200
    assert _parse(held.json()["held_until"]) > datetime.now(timezone.utc)

    listing = f"/api/v1/availability?doctor_id={world['doctor']['id']}&available=true"
    assert [s["id"] for s in (await client.get(listing, headers=alice["headers"])).json()["items"]] == [slot_id]
    assert (await client.get(listing, headers=bob["headers"])).json()["items"] == []
    assert (await client.get(listing)).json()["items"] == []

    assert (await client.post(f"/api/v1/availability/{slot_id}/hold", headers=bob["headers"])).status_code == 409
    bob_books = await client.post("/api/v1/appointments", headers=bob["headers"], json=_payload(world, bob["patient"]["id"]))
    assert bob_books.status_code == 409

    alice_books = await client.post("/api/v1/appointments", headers=alice["headers"], json=_payload(world, alice["patient"]["id"]))
    assert alice_books.status_code == 201


async def test_expired_hold_frees_the_slot(client: AsyncClient, admin_client: AsyncClient) -> None:
    world = await _world(admin_client)
    alice, bob = await register_patient(client), await register_patient(client)
    await client.post(f"/api/v1/availability/{world['slot']['id']}/hold", headers=alice["headers"])
    await _expire_hold(world["slot"]["id"])
    resp = await client.post("/api/v1/appointments", headers=bob["headers"], json=_payload(world, bob["patient"]["id"]))
    assert resp.status_code == 201


async def test_new_hold_releases_the_previous_one(client: AsyncClient, admin_client: AsyncClient) -> None:
    world = await _world(admin_client)
    second = await make_availability(admin_client, world["doctor"]["id"], world["clinic"]["id"], **_at(80))
    alice, bob = await register_patient(client), await register_patient(client)

    await client.post(f"/api/v1/availability/{world['slot']['id']}/hold", headers=alice["headers"])
    await client.post(f"/api/v1/availability/{second['id']}/hold", headers=alice["headers"])
    assert (await client.post(f"/api/v1/availability/{world['slot']['id']}/hold", headers=bob["headers"])).status_code == 200


async def test_release_hold(client: AsyncClient, admin_client: AsyncClient) -> None:
    world = await _world(admin_client)
    alice, bob = await register_patient(client), await register_patient(client)
    path = f"/api/v1/availability/{world['slot']['id']}/hold"
    await client.post(path, headers=alice["headers"])
    assert (await client.delete(path, headers=bob["headers"])).status_code == 204  # not bob's: no effect
    assert (await client.post(path, headers=bob["headers"])).status_code == 409
    assert (await client.delete(path, headers=alice["headers"])).status_code == 204
    assert (await client.post(path, headers=bob["headers"])).status_code == 200


async def test_only_patients_hold_slots(client: AsyncClient, admin_client: AsyncClient) -> None:
    world = await _world(admin_client)
    path = f"/api/v1/availability/{world['slot']['id']}/hold"
    assert (await client.post(path)).status_code == 401
    assert (await admin_client.post(path)).status_code == 403


# --- Status rules & cancellation policy -----------------------------------------------


async def test_status_transitions_are_enforced(admin_client: AsyncClient) -> None:
    world = await _world(admin_client)
    appt = (await admin_client.post("/api/v1/appointments", json=_payload(world, (await make_patient(admin_client))["id"]))).json()
    path = f"/api/v1/appointments/{appt['id']}"

    skipped = await admin_client.patch(path, json={"status": "completed"})  # pending -> completed
    assert skipped.status_code == 409 and skipped.json()["error"]["code"] == "invalid_status_transition"
    assert (await admin_client.patch(path, json={"status": "confirmed"})).status_code == 200
    early = await admin_client.patch(path, json={"status": "completed"})  # before it starts
    assert early.status_code == 409
    assert (await admin_client.patch(path, json={"status": "cancelled"})).status_code == 200
    assert (await admin_client.patch(path, json={"status": "confirmed"})).status_code == 409  # cancelled is final


async def test_patient_cancellation_records_who_and_why(client: AsyncClient, admin_client: AsyncClient) -> None:
    world = await _world(admin_client)
    alice = await register_patient(client)
    appt = (await client.post("/api/v1/appointments", headers=alice["headers"], json=_payload(world, alice["patient"]["id"]))).json()
    assert appt["cancellable_until"] is not None

    resp = await client.patch(
        f"/api/v1/appointments/{appt['id']}", headers=alice["headers"], json={"status": "cancelled", "cancellation_reason": "Travelling"}
    )
    assert resp.status_code == 200
    assert resp.json()["cancelled_at"] and resp.json()["cancellation_reason"] == "Travelling"
    assert (await _slot(admin_client, world["slot"]["id"]))["is_booked"] is False


async def test_patient_cannot_cancel_after_the_clinic_cutoff(client: AsyncClient, admin_client: AsyncClient) -> None:
    world = await _world(admin_client, cutoff_hours=24, slot_in_hours=5)
    alice = await register_patient(client)
    appt = (await client.post("/api/v1/appointments", headers=alice["headers"], json=_payload(world, alice["patient"]["id"]))).json()
    path = f"/api/v1/appointments/{appt['id']}"

    late = await client.patch(path, headers=alice["headers"], json={"status": "cancelled"})
    assert late.status_code == 409 and late.json()["error"]["code"] == "cancellation_window_closed"
    # The clinic can still cancel.
    assert (await admin_client.patch(path, json={"status": "cancelled"})).status_code == 200


async def test_cutoff_is_per_clinic(client: AsyncClient, admin_client: AsyncClient) -> None:
    world = await _world(admin_client, cutoff_hours=2, slot_in_hours=5)
    alice = await register_patient(client)
    appt = (await client.post("/api/v1/appointments", headers=alice["headers"], json=_payload(world, alice["patient"]["id"]))).json()
    resp = await client.patch(f"/api/v1/appointments/{appt['id']}", headers=alice["headers"], json={"status": "cancelled"})
    assert resp.status_code == 200


async def test_cancellation_reason_requires_cancelling(admin_client: AsyncClient) -> None:
    world = await _world(admin_client)
    appt = (await admin_client.post("/api/v1/appointments", json=_payload(world, (await make_patient(admin_client))["id"]))).json()
    resp = await admin_client.patch(f"/api/v1/appointments/{appt['id']}", json={"notes": "x", "cancellation_reason": "why"})
    assert resp.status_code == 422


# --- Rescheduling ------------------------------------------------------------------------


async def test_patient_reschedules_to_another_slot(client: AsyncClient, admin_client: AsyncClient) -> None:
    world = await _world(admin_client)
    other_clinic = await make_clinic(admin_client, cancellation_cutoff_hours=6)
    new_slot = await make_availability(admin_client, world["doctor"]["id"], other_clinic["id"], **_at(96))
    alice = await register_patient(client)
    appt = (await client.post("/api/v1/appointments", headers=alice["headers"], json=_payload(world, alice["patient"]["id"]))).json()
    await admin_client.patch(f"/api/v1/appointments/{appt['id']}", json={"status": "confirmed"})

    moved = await client.post(
        f"/api/v1/appointments/{appt['id']}/reschedule", headers=alice["headers"], json={"availability_id": new_slot["id"]}
    )
    assert moved.status_code == 200, moved.text
    body = moved.json()
    assert body["availability_id"] == new_slot["id"]
    assert body["clinic_id"] == other_clinic["id"]
    assert body["status"] == "pending"  # the clinic confirms the new time
    assert (await _slot(admin_client, world["slot"]["id"]))["is_booked"] is False
    assert (await _slot(admin_client, new_slot["id"]))["is_booked"] is True
    # New deadline follows the new clinic's policy (6h before).
    assert _parse(body["scheduled_start"]) - _parse(body["cancellable_until"]) == timedelta(hours=6)


async def test_reschedule_rules(client: AsyncClient, admin_client: AsyncClient) -> None:
    world = await _world(admin_client)
    alice = await register_patient(client)
    appt = (await client.post("/api/v1/appointments", headers=alice["headers"], json=_payload(world, alice["patient"]["id"]))).json()
    path = f"/api/v1/appointments/{appt['id']}/reschedule"

    other_doctor = await make_doctor(admin_client)
    their_slot = await make_availability(admin_client, other_doctor["id"], world["clinic"]["id"], **_at(90))
    assert (await client.post(path, headers=alice["headers"], json={"availability_id": their_slot["id"]})).status_code == 422

    taken = await make_availability(admin_client, world["doctor"]["id"], world["clinic"]["id"], **_at(91))
    await admin_client.post("/api/v1/appointments", json=_payload(world, (await make_patient(admin_client))["id"], slot=taken))
    assert (await client.post(path, headers=alice["headers"], json={"availability_id": taken["id"]})).status_code == 409

    bob = await register_patient(client)
    free = await make_availability(admin_client, world["doctor"]["id"], world["clinic"]["id"], **_at(92))
    assert (await client.post(path, headers=bob["headers"], json={"availability_id": free["id"]})).status_code == 404


async def test_reschedule_after_cutoff_is_refused(client: AsyncClient, admin_client: AsyncClient) -> None:
    world = await _world(admin_client, cutoff_hours=24, slot_in_hours=5)
    later = await make_availability(admin_client, world["doctor"]["id"], world["clinic"]["id"], **_at(100))
    alice = await register_patient(client)
    appt = (await client.post("/api/v1/appointments", headers=alice["headers"], json=_payload(world, alice["patient"]["id"]))).json()
    resp = await client.post(
        f"/api/v1/appointments/{appt['id']}/reschedule", headers=alice["headers"], json={"availability_id": later["id"]}
    )
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "cancellation_window_closed"


async def test_concurrent_reschedule_and_booking_of_one_slot(client: AsyncClient, admin_client: AsyncClient) -> None:
    world = await _world(admin_client)
    target = await make_availability(admin_client, world["doctor"]["id"], world["clinic"]["id"], **_at(120))
    alice = await register_patient(client)
    appt = (await client.post("/api/v1/appointments", headers=alice["headers"], json=_payload(world, alice["patient"]["id"]))).json()
    other = await make_patient(admin_client)

    moved, booked = await asyncio.gather(
        client.post(f"/api/v1/appointments/{appt['id']}/reschedule", headers=alice["headers"], json={"availability_id": target["id"]}),
        admin_client.post("/api/v1/appointments", json=_payload(world, other["id"], slot=target)),
    )
    assert sorted([moved.status_code, booked.status_code]) in ([200, 409], [201, 409]), (moved.text, booked.text)


# --- Slot edits can't break bookings --------------------------------------------------------


async def test_booked_slot_cannot_be_freed_or_moved_directly(admin_client: AsyncClient) -> None:
    world = await _world(admin_client)
    await admin_client.post("/api/v1/appointments", json=_payload(world, (await make_patient(admin_client))["id"]))
    path = f"/api/v1/availability/{world['slot']['id']}"
    assert (await admin_client.patch(path, json={"is_booked": False})).status_code == 409
    assert (await admin_client.patch(path, json=_at(200))).status_code == 409


async def test_missing_deadline_falls_back_to_clinic_policy(client: AsyncClient, admin_client: AsyncClient) -> None:
    """Appointments created outside the booking service (e.g. imports) still respect the cutoff."""
    from app.models.scheduling import Appointment

    world = await _world(admin_client, cutoff_hours=24, slot_in_hours=5)
    alice = await register_patient(client)
    appt = (await client.post("/api/v1/appointments", headers=alice["headers"], json=_payload(world, alice["patient"]["id"]))).json()
    async with AsyncSessionLocal() as db:
        row = await db.get(Appointment, uuid.UUID(appt["id"]))
        row.cancellable_until = None
        await db.commit()

    resp = await client.patch(f"/api/v1/appointments/{appt['id']}", headers=alice["headers"], json={"status": "cancelled"})
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "cancellation_window_closed"
