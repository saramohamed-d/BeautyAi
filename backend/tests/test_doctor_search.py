"""Sprint 6: GET /doctors/search — structured doctor matching."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from httpx import AsyncClient

from app.db.session import AsyncSessionLocal
from app.models.procedure import DoctorProcedure
from tests.factories import make_availability, make_clinic, make_doctor, make_procedure, register_patient


def _at(hours: float) -> dict:
    start = datetime.now(timezone.utc) + timedelta(hours=hours)
    return {"start_time": start.isoformat(), "end_time": (start + timedelta(minutes=30)).isoformat()}


async def _price(doctor: dict, procedure: dict, clinic: dict, price: int) -> None:
    async with AsyncSessionLocal() as db:
        db.add(
            DoctorProcedure(
                doctor_id=uuid.UUID(doctor["id"]),
                procedure_id=uuid.UUID(procedure["id"]),
                clinic_id=uuid.UUID(clinic["id"]),
                price=Decimal(price),
            )
        )
        await db.commit()


async def _verified_doctor(admin_client: AsyncClient, specialty: str, **overrides) -> dict:
    doctor = await make_doctor(admin_client, specialty=specialty, **overrides)
    resp = await admin_client.patch(f"/api/v1/doctors/{doctor['id']}", json={"verification_status": "verified"})
    return resp.json()


async def _search(client: AsyncClient, **params) -> list[dict]:
    resp = await client.get("/api/v1/doctors/search", params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()["items"]


async def test_search_is_public_and_returns_next_slot_price_and_clinics(client: AsyncClient, admin_client: AsyncClient) -> None:
    specialty = f"Derm-{uuid.uuid4().hex[:6]}"
    doctor = await _verified_doctor(admin_client, specialty)
    clinic = await make_clinic(admin_client, city="Cairo")
    later = await make_availability(admin_client, doctor["id"], clinic["id"], **_at(50))
    sooner = await make_availability(admin_client, doctor["id"], clinic["id"], **_at(20))
    procedure = await make_procedure(admin_client)
    await _price(doctor, procedure, clinic, 750)

    [result] = await _search(client, specialty=specialty)
    assert result["doctor"]["id"] == doctor["id"]
    assert result["next_slot"]["id"] == sooner["id"] != later["id"]
    assert result["price_from"] == 750
    assert [c["id"] for c in result["clinics"]] == [clinic["id"]]


async def test_unverified_doctors_are_hidden_by_default(client: AsyncClient, admin_client: AsyncClient) -> None:
    specialty = f"Derm-{uuid.uuid4().hex[:6]}"
    pending = await make_doctor(admin_client, specialty=specialty, verification_status="pending")
    assert await _search(client, specialty=specialty) == []
    assert [r["doctor"]["id"] for r in await _search(client, specialty=specialty, verified_only="false")] == [pending["id"]]


async def test_sorted_by_soonest_availability(client: AsyncClient, admin_client: AsyncClient) -> None:
    specialty = f"Derm-{uuid.uuid4().hex[:6]}"
    clinic = await make_clinic(admin_client)
    late, early, none = [await _verified_doctor(admin_client, specialty) for _ in range(3)]
    await make_availability(admin_client, late["id"], clinic["id"], **_at(90))
    await make_availability(admin_client, early["id"], clinic["id"], **_at(10))

    ids = [r["doctor"]["id"] for r in await _search(client, specialty=specialty)]
    assert ids == [early["id"], late["id"], none["id"]]  # doctors without slots last


async def test_booked_and_held_slots_are_not_next_slot(client: AsyncClient, admin_client: AsyncClient) -> None:
    specialty = f"Derm-{uuid.uuid4().hex[:6]}"
    doctor = await _verified_doctor(admin_client, specialty)
    clinic = await make_clinic(admin_client)
    held = await make_availability(admin_client, doctor["id"], clinic["id"], **_at(10))
    free = await make_availability(admin_client, doctor["id"], clinic["id"], **_at(30))
    alice, bob = await register_patient(client), await register_patient(client)
    await client.post(f"/api/v1/availability/{held['id']}/hold", headers=alice["headers"])

    anonymous = await _search(client, specialty=specialty)
    assert anonymous[0]["next_slot"]["id"] == free["id"]
    as_alice = (await client.get("/api/v1/doctors/search", params={"specialty": specialty}, headers=alice["headers"])).json()
    assert as_alice["items"][0]["next_slot"]["id"] == held["id"]  # your own hold stays visible to you
    as_bob = (await client.get("/api/v1/doctors/search", params={"specialty": specialty}, headers=bob["headers"])).json()
    assert as_bob["items"][0]["next_slot"]["id"] == free["id"]


async def test_filter_by_city(client: AsyncClient, admin_client: AsyncClient) -> None:
    specialty = f"Derm-{uuid.uuid4().hex[:6]}"
    city = f"City-{uuid.uuid4().hex[:6]}"
    local, remote = await _verified_doctor(admin_client, specialty), await _verified_doctor(admin_client, specialty)
    here, there = await make_clinic(admin_client, city=city), await make_clinic(admin_client, city="Elsewhere")
    await make_availability(admin_client, local["id"], here["id"], **_at(10))
    await make_availability(admin_client, remote["id"], there["id"], **_at(5))

    results = await _search(client, specialty=specialty, city=city)
    assert [r["doctor"]["id"] for r in results] == [local["id"]]
    assert results[0]["clinics"][0]["city"] == city


async def test_filter_by_procedure_and_price(client: AsyncClient, admin_client: AsyncClient) -> None:
    specialty = f"Derm-{uuid.uuid4().hex[:6]}"
    clinic = await make_clinic(admin_client)
    procedure = await make_procedure(admin_client)
    cheap, pricey, other = [await _verified_doctor(admin_client, specialty) for _ in range(3)]
    await _price(cheap, procedure, clinic, 400)
    await _price(pricey, procedure, clinic, 2000)

    offering = await _search(client, specialty=specialty, procedure_id=procedure["id"], sort="price")
    assert [r["doctor"]["id"] for r in offering] == [cheap["id"], pricey["id"]]  # `other` doesn't offer it
    affordable = await _search(client, specialty=specialty, procedure_id=procedure["id"], max_price=500)
    assert [r["doctor"]["id"] for r in affordable] == [cheap["id"]]


async def test_filter_by_available_before_and_text(client: AsyncClient, admin_client: AsyncClient) -> None:
    specialty = f"Derm-{uuid.uuid4().hex[:6]}"
    clinic = await make_clinic(admin_client)
    soon = await _verified_doctor(admin_client, specialty, full_name=f"Dr Soon {uuid.uuid4().hex[:4]}")
    later = await _verified_doctor(admin_client, specialty)
    await make_availability(admin_client, soon["id"], clinic["id"], **_at(10))
    await make_availability(admin_client, later["id"], clinic["id"], **_at(200))

    before = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    assert [r["doctor"]["id"] for r in await _search(client, specialty=specialty, available_before=before)] == [soon["id"]]
    assert [r["doctor"]["id"] for r in await _search(client, q=soon["full_name"])] == [soon["id"]]
