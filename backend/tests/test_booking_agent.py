"""
Sprint 10: the booking agent. The model only fills a BookingRequest; the
platform validates it, searches, ranks and words the answer, and nothing
is booked until the patient reserves an offered option and confirms.

Every test uses its own made-up city, so data from other tests can't
match its searches.
"""

import uuid
from collections.abc import Iterator
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient

from app.agents.llm import get_llm
from app.main import app
from tests.ai_helpers import assessment, booking, draft
from tests.factories import make_availability, make_clinic, make_doctor, register_patient

CAIRO = ZoneInfo("Africa/Cairo")


def _day(offset: int):
    return (datetime.now(CAIRO) + timedelta(days=offset)).date()


def _at(day_offset: int, hour: int, minute: int = 0) -> dict:
    start = datetime.combine(_day(day_offset), time(hour, minute), CAIRO)
    return {"start_time": start.isoformat(), "end_time": (start + timedelta(minutes=30)).isoformat()}


def _local(iso: str) -> datetime:
    return datetime.fromisoformat(iso).astimezone(CAIRO)


async def _verified_doctor(admin_client: AsyncClient, specialty: str = "Dermatology", **overrides) -> dict:
    doctor = await make_doctor(admin_client, specialty=specialty, **overrides)
    return (await admin_client.patch(f"/api/v1/doctors/{doctor['id']}", json={"verification_status": "verified"})).json()


async def _city_world(admin_client: AsyncClient) -> tuple[str, dict, dict]:
    city = f"Testcity{uuid.uuid4().hex[:8]}"
    clinic = await make_clinic(admin_client, city=city)
    doctor = await _verified_doctor(admin_client)
    return city, clinic, doctor


class ScriptLLM:
    name, model = "scripted", "scripted-1"

    def __init__(self, *drafts) -> None:
        self.drafts = list(drafts)

    async def respond(self, **_):
        return self.drafts.pop(0) if len(self.drafts) > 1 else self.drafts[0]


@pytest.fixture
def script() -> Iterator[callable]:
    def install(*drafts):
        llm = ScriptLLM(*drafts)  # one instance, so the script advances across turns
        app.dependency_overrides[get_llm] = lambda: llm

    yield install
    app.dependency_overrides.pop(get_llm, None)


async def _start(client: AsyncClient) -> tuple[dict, str]:
    patient = await register_patient(client)
    conversation = (await client.post("/api/v1/conversations", headers=patient["headers"], json={"accept_ai_terms": True})).json()
    return patient, conversation["id"]


async def _ask(client: AsyncClient, patient: dict, conversation_id: str, text: str = "Book me an appointment") -> dict:
    resp = await client.post(f"/api/v1/conversations/{conversation_id}/chat", headers=patient["headers"], json={"content": text})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _booking(turn: dict) -> dict:
    return turn["assistant_message"]["extra_data"]["booking"]


# --- Search and ranking ------------------------------------------------------------


async def test_time_of_day_and_preferred_time_in_local_time(client, admin_client, script) -> None:
    city, clinic, doctor = await _city_world(admin_client)
    for hour, minute in ((10, 0), (17, 30), (20, 0), (18, 45)):
        await make_availability(admin_client, doctor["id"], clinic["id"], **_at(1, hour, minute))
    tomorrow = _day(1).isoformat()
    script(draft(booking_request=booking(city=city, date_from=tomorrow, date_to=tomorrow, preferred_time="17:00")))
    patient, conversation_id = await _start(client)

    found = _booking(await _ask(client, patient, conversation_id))
    local_times = [_local(o["start_time"]).strftime("%H:%M") for o in found["options"]]
    # 17:00 → evening only (10:00 excluded); closest first; one doctor so up to 3 of their slots.
    assert local_times == ["17:30", "18:45", "20:00"]
    assert found["criteria"]["time_of_day"] == "evening" and found["relaxed"] == []


async def test_one_option_per_doctor_before_a_second_slot(client, admin_client, script) -> None:
    city, clinic, first = await _city_world(admin_client)
    second = await _verified_doctor(admin_client)
    for hour in (9, 10, 11):
        await make_availability(admin_client, first["id"], clinic["id"], **_at(2, hour))
    await make_availability(admin_client, second["id"], clinic["id"], **_at(3, 15))
    script(draft(booking_request=booking(city=city)))
    patient, conversation_id = await _start(client)

    options = _booking(await _ask(client, patient, conversation_id))["options"]
    assert [o["doctor"]["id"] for o in options] == [first["id"], second["id"], first["id"]]


async def test_relaxes_time_then_dates_then_city_and_says_so(client, admin_client, script) -> None:
    city, clinic, doctor = await _city_world(admin_client)
    await make_availability(admin_client, doctor["id"], clinic["id"], **_at(4, 19))
    tomorrow = _day(1).isoformat()
    script(draft(booking_request=booking(city=city, date_from=tomorrow, date_to=tomorrow, time_of_day="morning")))
    patient, conversation_id = await _start(client)

    turn = await _ask(client, patient, conversation_id)
    found = _booking(turn)
    assert found["relaxed"] == ["time_of_day", "dates"]
    assert [_local(o["start_time"]).hour for o in found["options"]] == [19]
    assert "couldn't find a time matching exactly" in turn["assistant_message"]["content"]

    script(draft(booking_request=booking(city=f"Nowhere{uuid.uuid4().hex[:6]}")))
    relaxed_city = _booking(await _ask(client, patient, conversation_id))
    assert "city" in relaxed_city["relaxed"] and relaxed_city["options"]


async def test_only_bookable_verified_slots_are_offered(client, admin_client, script) -> None:
    city, clinic, doctor = await _city_world(admin_client)
    # A doctor whose verification was withdrawn after their slots were published.
    unverified = await make_doctor(admin_client, specialty="Dermatology")
    await make_availability(admin_client, unverified["id"], clinic["id"], **_at(1, 12))
    await admin_client.patch(f"/api/v1/doctors/{unverified['id']}", json={"verification_status": "pending"})
    held = await make_availability(admin_client, doctor["id"], clinic["id"], **_at(1, 13))
    free = await make_availability(admin_client, doctor["id"], clinic["id"], **_at(1, 14))
    await make_availability(admin_client, doctor["id"], clinic["id"], **_at(-1, 14))  # past
    other = await register_patient(client)
    assert (await client.post(f"/api/v1/availability/{held['id']}/hold", headers=other["headers"])).status_code == 200

    script(draft(booking_request=booking(city=city)))
    patient, conversation_id = await _start(client)
    assert [o["availability_id"] for o in _booking(await _ask(client, patient, conversation_id))["options"]] == [free["id"]]


async def test_local_date_boundary(client, admin_client, script) -> None:
    """1 am tomorrow in Cairo is still 'today' in UTC; it must count as tomorrow."""
    city, clinic, doctor = await _city_world(admin_client)
    early = await make_availability(admin_client, doctor["id"], clinic["id"], **_at(1, 1))
    tomorrow = _day(1).isoformat()
    script(draft(booking_request=booking(city=city, date_from=tomorrow, date_to=tomorrow)))
    patient, conversation_id = await _start(client)
    found = _booking(await _ask(client, patient, conversation_id))
    assert [o["availability_id"] for o in found["options"]] == [early["id"]] and found["relaxed"] == []


# --- In the chat ------------------------------------------------------------------------


async def test_platform_words_the_reply_and_model_cannot_state_times(client, admin_client, script) -> None:
    city, clinic, doctor = await _city_world(admin_client)
    await make_availability(admin_client, doctor["id"], clinic["id"], **_at(2, 16))
    script(draft("Great news, Dr. Invented is free at 3 PM!", booking_request=booking(city=city)))
    patient, conversation_id = await _start(client)
    turn = await _ask(client, patient, conversation_id)
    assert "Invented" not in turn["assistant_message"]["content"]
    assert turn["assistant_message"]["content"].startswith("Here are the best matching times")


async def test_specialty_falls_back_to_the_assessment(client, admin_client, script) -> None:
    city, clinic, _ = await _city_world(admin_client)
    aesthetic = await _verified_doctor(admin_client, specialty="Aesthetic Medicine")
    await make_availability(admin_client, aesthetic["id"], clinic["id"], **_at(2, 12))
    script(
        draft(assessment=assessment(suggested_specialty="Aesthetic Medicine"), concern="anti_aging", body_area="face",
              duration="1 year", symptoms=[]),
        draft(booking_request=booking(city=city)),
    )
    patient, conversation_id = await _start(client)
    await _ask(client, patient, conversation_id, "Lines on my face for a year, no symptoms")
    found = _booking(await _ask(client, patient, conversation_id, "Yes please find me one"))
    assert found["criteria"]["specialty"] == "Aesthetic Medicine"
    assert [o["doctor"]["id"] for o in found["options"]] == [aesthetic["id"]]


async def test_no_booking_during_a_possible_emergency(client, admin_client, script) -> None:
    city, clinic, doctor = await _city_world(admin_client)
    await make_availability(admin_client, doctor["id"], clinic["id"], **_at(2, 12))
    script(draft(risk_level="high", booking_request=booking(city=city)))
    patient, conversation_id = await _start(client)
    turn = await _ask(client, patient, conversation_id)
    assert turn["assistant_message"]["extra_data"]["booking"] is None


# --- Reserving an option --------------------------------------------------------------------


async def test_reserve_only_offered_options_then_confirm_on_payment(client, admin_client, script) -> None:
    city, clinic, doctor = await _city_world(admin_client)
    offered = await make_availability(admin_client, doctor["id"], clinic["id"], **_at(2, 12))
    script(draft(booking_request=booking(city=city)))
    patient, conversation_id = await _start(client)
    await _ask(client, patient, conversation_id)
    path = f"/api/v1/conversations/{conversation_id}/booking/reserve"

    not_offered = await make_availability(admin_client, doctor["id"], clinic["id"], **_at(9, 12))
    assert (await client.post(path, headers=patient["headers"], json={"availability_id": not_offered["id"]})).status_code == 404
    stranger = await register_patient(client)
    assert (await client.post(path, headers=stranger["headers"], json={"availability_id": offered["id"]})).status_code == 404

    reserved = await client.post(path, headers=patient["headers"], json={"availability_id": offered["id"]})
    assert reserved.status_code == 200, reserved.text
    body = reserved.json()
    assert body["doctor"]["id"] == doctor["id"] and body["clinic"]["id"] == clinic["id"] and body["hold"]["held_until"]
    assert body["message"]["extra_data"]["kind"] == "booking_hold"
    transcript = (await client.get(f"/api/v1/conversations/{conversation_id}", headers=patient["headers"])).json()["messages"]
    assert transcript[-1]["extra_data"]["kind"] == "booking_hold"

    # Nothing is booked until the patient confirms on the payment screen.
    assert (await admin_client.get(f"/api/v1/availability/{offered['id']}")).json()["is_booked"] is False
    confirmed = await client.post(
        "/api/v1/appointments",
        headers=patient["headers"],
        json={"patient_id": patient["patient"]["id"], "doctor_id": doctor["id"], "clinic_id": clinic["id"],
              "availability_id": offered["id"], "scheduled_start": offered["start_time"], "scheduled_end": offered["end_time"]},
    )
    assert confirmed.status_code == 201


async def test_reserving_a_time_someone_else_took(client, admin_client, script) -> None:
    city, clinic, doctor = await _city_world(admin_client)
    slot = await make_availability(admin_client, doctor["id"], clinic["id"], **_at(2, 12))
    script(draft(booking_request=booking(city=city)))
    patient, conversation_id = await _start(client)
    await _ask(client, patient, conversation_id)
    rival = await register_patient(client)
    await client.post(f"/api/v1/availability/{slot['id']}/hold", headers=rival["headers"])

    resp = await client.post(
        f"/api/v1/conversations/{conversation_id}/booking/reserve", headers=patient["headers"], json={"availability_id": slot["id"]}
    )
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "slot_unavailable"


# --- Demo AI ----------------------------------------------------------------------------------


async def test_demo_understands_book_me_tomorrow_at_5pm(client, admin_client) -> None:
    clinic = await make_clinic(admin_client, city="Cairo")
    doctor = await _verified_doctor(admin_client)
    await make_availability(admin_client, doctor["id"], clinic["id"], **_at(1, 17))
    patient, conversation_id = await _start(client)
    turn = await _ask(client, patient, conversation_id, "Book me tomorrow with a dermatologist at 5 PM in Cairo")
    found = _booking(turn)
    assert found["criteria"] == {
        "specialty": "Dermatology", "city": "Cairo", "date_from": _day(1).isoformat(), "date_to": _day(1).isoformat(),
        "time_of_day": "evening", "preferred_time": "17:00", "doctor_name": None,
    }
    first = _local(found["options"][0]["start_time"])
    assert first.date() == _day(1) and first.strftime("%H:%M") == "17:00"
    assert all(o["doctor"]["specialty"] == "Dermatology" for o in found["options"])
