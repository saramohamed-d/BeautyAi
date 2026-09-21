"""Sprint 13: the clinic admin dashboard — team, services and prices, opening hours, slot generation, appointments."""

import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from httpx import AsyncClient

from tests.factories import (
    make_availability,
    make_clinic,
    make_clinic_admin,
    make_doctor,
    make_procedure,
    register_patient,
)

CAIRO = ZoneInfo("Africa/Cairo")

# Sunday to Thursday, 10:00-13:00 (Egypt's working week).
WEEK = [{"weekday": d, "opens_at": "10:00:00", "closes_at": "13:00:00", "is_closed": False} for d in (6, 0, 1, 2, 3)]


def _next_weekday(target: int, *, weeks: int = 0) -> date:
    """The next date (in Cairo) with this weekday, always in the future."""
    today = datetime.now(CAIRO).date()
    ahead = (target - today.weekday()) % 7 or 7
    return today + timedelta(days=ahead + 7 * weeks)


async def _clinic_world(admin_client: AsyncClient, **clinic_overrides) -> dict:
    clinic = await make_clinic(admin_client, **clinic_overrides)
    headers = await make_clinic_admin(clinic["id"])
    doctor = await make_doctor(admin_client)
    return {"clinic": clinic, "headers": headers, "doctor": doctor}


async def _add_doctor(client: AsyncClient, world: dict, doctor_id: str, **extra):
    return await client.post(
        f"/api/v1/clinics/{world['clinic']['id']}/staff",
        headers=world["headers"],
        json={"role": "doctor", "doctor_id": doctor_id, **extra},
    )


async def _set_hours(client: AsyncClient, world: dict, days=None):
    return await client.put(
        f"/api/v1/clinics/{world['clinic']['id']}/hours", headers=world["headers"], json={"days": days or WEEK}
    )


# --- The team ------------------------------------------------------------------------------


async def test_clinic_admin_manages_its_doctors(client: AsyncClient, admin_client: AsyncClient) -> None:
    world = await _clinic_world(admin_client)
    added = await _add_doctor(client, world, world["doctor"]["id"], consultation_fee=450)
    assert added.status_code == 201, added.text
    member = added.json()
    assert member["full_name"] == world["doctor"]["full_name"]  # copied from the profile
    assert member["verification_status"] == "verified"
    assert float(member["consultation_fee"]) == 450

    # The same doctor can't be added twice.
    assert (await _add_doctor(client, world, world["doctor"]["id"])).status_code == 409

    # The list holds the clinic's own admin login as well as the doctor.
    listed = (await client.get(f"/api/v1/clinics/{world['clinic']['id']}/staff", headers=world["headers"])).json()
    assert [m["id"] for m in listed if m["role"] == "doctor"] == [member["id"]]
    assert any(m["role"] == "clinic_admin" for m in listed)

    # The fee here is the one patients are quoted (Sprint 11).
    slot = await make_availability(admin_client, world["doctor"]["id"], world["clinic"]["id"])
    patient = await register_patient(client)
    quote = (
        await client.get(f"/api/v1/payments/quote?availability_id={slot['id']}", headers=patient["headers"])
    ).json()
    assert float(quote["amount"]) == 450

    updated = await client.patch(
        f"/api/v1/clinics/{world['clinic']['id']}/staff/{member['id']}",
        headers=world["headers"],
        json={"consultation_fee": 600, "phone": "+201000000000"},
    )
    assert updated.status_code == 200
    assert float(updated.json()["consultation_fee"]) == 600

    removed = await client.delete(
        f"/api/v1/clinics/{world['clinic']['id']}/staff/{member['id']}", headers=world["headers"]
    )
    assert removed.status_code == 204
    after = (await client.get(f"/api/v1/clinics/{world['clinic']['id']}/staff", headers=world["headers"])).json()
    assert [m["id"] for m in after if m["role"] == "doctor"] == []


async def test_non_doctor_staff_need_a_name(client: AsyncClient, admin_client: AsyncClient) -> None:
    world = await _clinic_world(admin_client)
    url = f"/api/v1/clinics/{world['clinic']['id']}/staff"
    assert (await client.post(url, headers=world["headers"], json={"role": "clinic_admin"})).status_code == 422
    receptionist = await client.post(
        url, headers=world["headers"], json={"role": "clinic_admin", "full_name": "Yasmin Adel"}
    )
    assert receptionist.status_code == 201
    assert receptionist.json()["doctor_id"] is None


# --- Opening hours --------------------------------------------------------------------------


async def test_opening_hours_round_trip(client: AsyncClient, admin_client: AsyncClient) -> None:
    world = await _clinic_world(admin_client)
    saved = await _set_hours(client, world)
    assert saved.status_code == 200
    assert [day["weekday"] for day in saved.json()] == [0, 1, 2, 3, 6]  # returned in week order

    # Sending fewer days removes the rest (that day is simply closed).
    trimmed = await _set_hours(client, world, days=WEEK[:2])
    assert {day["weekday"] for day in trimmed.json()} == {day["weekday"] for day in WEEK[:2]}

    closing_before_opening = await _set_hours(
        client, world, days=[{"weekday": 0, "opens_at": "18:00:00", "closes_at": "09:00:00"}]
    )
    assert closing_before_opening.status_code == 422
    duplicate_day = await _set_hours(client, world, days=[WEEK[0], WEEK[0]])
    assert duplicate_day.status_code == 422


# --- Slot generation ------------------------------------------------------------------------


async def test_generate_slots_from_opening_hours(client: AsyncClient, admin_client: AsyncClient) -> None:
    world = await _clinic_world(admin_client, slot_duration_minutes=60)
    await _add_doctor(client, world, world["doctor"]["id"])
    await _set_hours(client, world)

    monday = _next_weekday(0)
    result = await client.post(
        f"/api/v1/clinics/{world['clinic']['id']}/slots/generate",
        headers=world["headers"],
        json={"doctor_id": world["doctor"]["id"], "date_from": monday.isoformat(), "date_to": monday.isoformat()},
    )
    assert result.status_code == 200, result.text
    body = result.json()
    # 10:00-13:00 in one-hour slots = 3.
    assert (body["created"], body["skipped_existing"], body["slot_minutes"]) == (3, 0, 60)

    slots = (
        await admin_client.get(
            f"/api/v1/availability?doctor_id={world['doctor']['id']}&clinic_id={world['clinic']['id']}&page_size=100"
        )
    ).json()["items"]
    local_starts = sorted(datetime.fromisoformat(s["start_time"]).astimezone(CAIRO).strftime("%H:%M") for s in slots)
    assert local_starts == ["10:00", "11:00", "12:00"]

    # Running it again changes nothing.
    again = (
        await client.post(
            f"/api/v1/clinics/{world['clinic']['id']}/slots/generate",
            headers=world["headers"],
            json={"doctor_id": world["doctor"]["id"], "date_from": monday.isoformat(), "date_to": monday.isoformat()},
        )
    ).json()
    assert (again["created"], again["skipped_existing"]) == (0, 3)


async def test_generation_skips_closed_days_and_the_past(client: AsyncClient, admin_client: AsyncClient) -> None:
    world = await _clinic_world(admin_client, slot_duration_minutes=90)
    await _add_doctor(client, world, world["doctor"]["id"])
    # One open weekday, deliberately not today, so "today's remaining hours"
    # can't change the count; another day exists but is marked closed.
    open_day = (datetime.now(CAIRO).date().weekday() + 2) % 7
    closed_day = (open_day + 1) % 7
    await _set_hours(
        client,
        world,
        days=[
            {"weekday": open_day, "opens_at": "09:00:00", "closes_at": "12:00:00"},
            {"weekday": closed_day, "opens_at": "09:00:00", "closes_at": "12:00:00", "is_closed": True},
        ],
    )
    target = _next_weekday(open_day)
    result = (
        await client.post(
            f"/api/v1/clinics/{world['clinic']['id']}/slots/generate",
            headers=world["headers"],
            json={
                "doctor_id": world["doctor"]["id"],
                "date_from": (target - timedelta(days=7)).isoformat(),  # a week in the past
                "date_to": target.isoformat(),
            },
        )
    ).json()
    # Only the future occurrence counts: 09:00-12:00 in 90-minute slots = 2.
    assert result["created"] == 2
    assert result["closed_days"] > 0

    slots = (
        await admin_client.get(
            f"/api/v1/availability?doctor_id={world['doctor']['id']}&clinic_id={world['clinic']['id']}&page_size=100"
        )
    ).json()["items"]
    assert len(slots) == 2
    assert all(datetime.fromisoformat(s["start_time"]).date() == target for s in slots)


async def test_generation_rules(client: AsyncClient, admin_client: AsyncClient) -> None:
    world = await _clinic_world(admin_client)
    url = f"/api/v1/clinics/{world['clinic']['id']}/slots/generate"
    monday = _next_weekday(0)

    # A doctor who isn't on the team.
    outsider = await make_doctor(admin_client)
    not_ours = await client.post(
        url,
        headers=world["headers"],
        json={"doctor_id": outsider["id"], "date_from": monday.isoformat(), "date_to": monday.isoformat()},
    )
    assert not_ours.status_code == 409 and not_ours.json()["error"]["code"] == "doctor_not_at_clinic"

    await _add_doctor(client, world, world["doctor"]["id"])
    no_hours = await client.post(
        url,
        headers=world["headers"],
        json={"doctor_id": world["doctor"]["id"], "date_from": monday.isoformat(), "date_to": monday.isoformat()},
    )
    assert no_hours.status_code == 422 and no_hours.json()["error"]["code"] == "no_opening_hours"

    await _set_hours(client, world)
    too_long = await client.post(
        url,
        headers=world["headers"],
        json={
            "doctor_id": world["doctor"]["id"],
            "date_from": monday.isoformat(),
            "date_to": (monday + timedelta(days=200)).isoformat(),
        },
    )
    assert too_long.status_code == 422

    backwards = await client.post(
        url,
        headers=world["headers"],
        json={
            "doctor_id": world["doctor"]["id"],
            "date_from": monday.isoformat(),
            "date_to": (monday - timedelta(days=1)).isoformat(),
        },
    )
    assert backwards.status_code == 422


async def test_unverified_doctors_get_no_slots(client: AsyncClient, admin_client: AsyncClient) -> None:
    world = await _clinic_world(admin_client)
    await _add_doctor(client, world, world["doctor"]["id"])
    await _set_hours(client, world)
    await admin_client.patch(f"/api/v1/doctors/{world['doctor']['id']}", json={"verification_status": "pending"})

    monday = _next_weekday(0)
    refused = await client.post(
        f"/api/v1/clinics/{world['clinic']['id']}/slots/generate",
        headers=world["headers"],
        json={"doctor_id": world["doctor"]["id"], "date_from": monday.isoformat(), "date_to": monday.isoformat()},
    )
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "doctor_not_verified"


async def test_free_slots_can_be_deleted_booked_ones_cannot(client: AsyncClient, admin_client: AsyncClient) -> None:
    world = await _clinic_world(admin_client)
    await _add_doctor(client, world, world["doctor"]["id"])
    free = await make_availability(admin_client, world["doctor"]["id"], world["clinic"]["id"])
    taken = await make_availability(
        admin_client,
        world["doctor"]["id"],
        world["clinic"]["id"],
        start_time=(datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
        end_time=(datetime.now(timezone.utc) + timedelta(days=2, minutes=30)).isoformat(),
    )
    patient = await register_patient(client)
    booked = await client.post(
        "/api/v1/appointments",
        headers=patient["headers"],
        json={
            "patient_id": patient["patient"]["id"], "doctor_id": world["doctor"]["id"],
            "clinic_id": world["clinic"]["id"], "availability_id": taken["id"],
            "scheduled_start": taken["start_time"], "scheduled_end": taken["end_time"],
        },
    )
    assert booked.status_code == 201

    base = f"/api/v1/clinics/{world['clinic']['id']}/slots"
    assert (await client.delete(f"{base}/{free['id']}", headers=world["headers"])).status_code == 204
    refused = await client.delete(f"{base}/{taken['id']}", headers=world["headers"])
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "slot_booked"

    # A slot at another clinic is not ours to delete.
    other = await _clinic_world(admin_client)
    elsewhere = await make_availability(admin_client, other["doctor"]["id"], other["clinic"]["id"])
    assert (await client.delete(f"{base}/{elsewhere['id']}", headers=world["headers"])).status_code == 404


# --- Services and prices ----------------------------------------------------------------------


async def test_services_and_prices(client: AsyncClient, admin_client: AsyncClient) -> None:
    # A name of its own, so the public search below can't match other tests' doctors.
    world = await _clinic_world(admin_client)
    world["doctor"] = await make_doctor(admin_client, full_name=f"Dr Peel {uuid.uuid4().hex[:8]}")
    await _add_doctor(client, world, world["doctor"]["id"])
    procedure = await make_procedure(admin_client, name="Chemical Peel")
    url = f"/api/v1/clinics/{world['clinic']['id']}/services"

    created = await client.post(
        url,
        headers=world["headers"],
        json={"doctor_id": world["doctor"]["id"], "procedure_id": procedure["id"], "price": 1500},
    )
    assert created.status_code == 201, created.text
    service = created.json()
    assert (service["procedure_name"], service["doctor_name"]) == ("Chemical Peel", world["doctor"]["full_name"])

    duplicate = await client.post(
        url,
        headers=world["headers"],
        json={"doctor_id": world["doctor"]["id"], "procedure_id": procedure["id"], "price": 1600},
    )
    assert duplicate.status_code == 409

    repriced = await client.patch(f"{url}/{service['id']}", headers=world["headers"], json={"price": 1200})
    assert float(repriced.json()["price"]) == 1200
    # The public doctor search shows the new price.
    found = (await client.get(f"/api/v1/doctors/search?q={world['doctor']['full_name']}")).json()["items"]
    assert any(row["doctor"]["id"] == world["doctor"]["id"] and row["price_from"] == 1200 for row in found)

    assert (await client.delete(f"{url}/{service['id']}", headers=world["headers"])).status_code == 204
    assert (await client.get(url, headers=world["headers"])).json() == []


async def test_services_need_a_doctor_on_the_team(client: AsyncClient, admin_client: AsyncClient) -> None:
    world = await _clinic_world(admin_client)
    procedure = await make_procedure(admin_client)
    refused = await client.post(
        f"/api/v1/clinics/{world['clinic']['id']}/services",
        headers=world["headers"],
        json={"doctor_id": world["doctor"]["id"], "procedure_id": procedure["id"], "price": 100},
    )
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "doctor_not_at_clinic"


# --- Dashboard and appointments -----------------------------------------------------------------


async def test_summary_counts_what_the_clinic_has(client: AsyncClient, admin_client: AsyncClient) -> None:
    world = await _clinic_world(admin_client)
    await _add_doctor(client, world, world["doctor"]["id"])
    procedure = await make_procedure(admin_client)
    await client.post(
        f"/api/v1/clinics/{world['clinic']['id']}/services",
        headers=world["headers"],
        json={"doctor_id": world["doctor"]["id"], "procedure_id": procedure["id"], "price": 900},
    )
    slot = await make_availability(admin_client, world["doctor"]["id"], world["clinic"]["id"])
    patient = await register_patient(client)
    await client.post(
        "/api/v1/appointments",
        headers=patient["headers"],
        json={
            "patient_id": patient["patient"]["id"], "doctor_id": world["doctor"]["id"],
            "clinic_id": world["clinic"]["id"], "availability_id": slot["id"],
            "scheduled_start": slot["start_time"], "scheduled_end": slot["end_time"],
        },
    )

    summary = (await client.get(f"/api/v1/clinics/{world['clinic']['id']}/summary", headers=world["headers"])).json()
    assert summary["doctors"] == 1
    assert summary["services"] == 1
    assert summary["upcoming"] == 1
    assert summary["pending"] == 1
    assert summary["open_slots"] == 0  # the only slot is now booked


async def test_clinic_admin_confirms_its_appointments(client: AsyncClient, admin_client: AsyncClient) -> None:
    world = await _clinic_world(admin_client)
    await _add_doctor(client, world, world["doctor"]["id"])
    slot = await make_availability(admin_client, world["doctor"]["id"], world["clinic"]["id"])
    patient = await register_patient(client)
    appointment = (
        await client.post(
            "/api/v1/appointments",
            headers=patient["headers"],
            json={
                "patient_id": patient["patient"]["id"], "doctor_id": world["doctor"]["id"],
                "clinic_id": world["clinic"]["id"], "availability_id": slot["id"],
                "scheduled_start": slot["start_time"], "scheduled_end": slot["end_time"],
            },
        )
    ).json()

    listed = (
        await client.get(f"/api/v1/appointments?clinic_id={world['clinic']['id']}", headers=world["headers"])
    ).json()
    assert [a["id"] for a in listed["items"]] == [appointment["id"]]

    confirmed = await client.patch(
        f"/api/v1/appointments/{appointment['id']}", headers=world["headers"], json={"status": "confirmed"}
    )
    assert confirmed.status_code == 200 and confirmed.json()["status"] == "confirmed"


# --- Permissions ------------------------------------------------------------------------------


async def test_only_the_clinics_own_admins_get_in(client: AsyncClient, admin_client: AsyncClient) -> None:
    world = await _clinic_world(admin_client)
    other = await _clinic_world(admin_client)
    patient = await register_patient(client)
    clinic_id = world["clinic"]["id"]

    for headers in (other["headers"], patient["headers"]):
        assert (await client.get(f"/api/v1/clinics/{clinic_id}/summary", headers=headers)).status_code == 403
        assert (await client.get(f"/api/v1/clinics/{clinic_id}/staff", headers=headers)).status_code == 403
        assert (await client.get(f"/api/v1/clinics/{clinic_id}/services", headers=headers)).status_code == 403
        assert (
            await client.put(f"/api/v1/clinics/{clinic_id}/hours", headers=headers, json={"days": WEEK})
        ).status_code == 403
    assert (await client.get(f"/api/v1/clinics/{clinic_id}/summary")).status_code == 401
    # Platform admins manage every clinic.
    assert (await admin_client.get(f"/api/v1/clinics/{clinic_id}/summary")).status_code == 200
    # An unknown clinic is a 404 even for a platform admin.
    assert (await admin_client.get(f"/api/v1/clinics/{uuid.uuid4()}/summary")).status_code == 404


async def test_session_lists_the_clinics_a_clinic_admin_manages(client: AsyncClient, admin_client: AsyncClient) -> None:
    """The dashboard needs to know which clinics to offer, straight from the session."""
    world = await _clinic_world(admin_client)
    me = (await client.get("/api/v1/auth/me", headers=world["headers"])).json()
    assert [c["id"] for c in me["clinics"]] == [world["clinic"]["id"]]
    assert me["clinics"][0]["name"] == world["clinic"]["name"]

    patient = await register_patient(client)
    assert (await client.get("/api/v1/auth/me", headers=patient["headers"])).json()["clinics"] == []
