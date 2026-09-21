"""Sprint 12: doctor sign-up, document uploads, admin approve/reject, and what being unverified blocks."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.audit import AuditEvent
from app.models.doctor import DoctorDocument
from app.storage import files
from tests.factories import TEST_PASSWORD, make_availability, make_clinic, make_doctor, register_patient, unique_email, unique_phone

PDF = b"%PDF-1.4\n" + b"x" * 512
PNG = b"\x89PNG\r\n\x1a\n" + b"y" * 512


def _registration(**overrides) -> dict:
    payload = {
        "full_name": "Dr Salma Fouad",
        "email": unique_email(),
        "phone": unique_phone(),
        "password": TEST_PASSWORD,
        "specialty": "Dermatology",
        "sub_specialty": "Laser",
        "license_number": f"EG-{uuid.uuid4().hex[:8]}",
        "years_experience": 9,
        "medical_degree": "MBBCh",
        "university": "Cairo University",
        "city": "Cairo",
    }
    payload.update(overrides)
    return payload


async def register_doctor(client: AsyncClient, **overrides) -> dict:
    resp = await client.post("/api/v1/auth/register/doctor", json=_registration(**overrides))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    body["headers"] = {"Authorization": f"Bearer {body['access_token']}"}
    return body


def _file(name: str = "licence.pdf", content: bytes = PDF, content_type: str = "application/pdf") -> dict:
    return {"file": (name, content, content_type)}


async def upload(client: AsyncClient, doctor: dict, document_type: str, **file_kwargs):
    return await client.post(
        f"/api/v1/doctors/{doctor['doctor']['id']}/documents",
        headers=doctor["headers"],
        data={"document_type": document_type},
        files=_file(**file_kwargs),
    )


async def ready_to_submit(client: AsyncClient) -> dict:
    doctor = await register_doctor(client)
    assert (await upload(client, doctor, "medical_license")).status_code == 201
    assert (await upload(client, doctor, "national_id", name="id.png", content=PNG, content_type="image/png")).status_code == 201
    return doctor


# --- Sign-up ------------------------------------------------------------------------------


async def test_doctor_signs_up_and_is_logged_in_but_unverified(client: AsyncClient) -> None:
    body = await register_doctor(client)
    assert body["user"]["role"] == "doctor" and body["user"]["status"] == "active"
    doctor = body["doctor"]
    assert doctor["verification_status"] == "pending"
    assert doctor["submitted_at"] is None
    assert (doctor["specialty"], doctor["university"], doctor["city"]) == ("Dermatology", "Cairo University", "Cairo")
    assert body["patient"] is None

    # The session restores the doctor profile, so the dashboard knows the status.
    me = (await client.get("/api/v1/auth/me", headers=body["headers"])).json()
    assert me["doctor"]["id"] == doctor["id"] and me["doctor"]["license_number"] == doctor["license_number"]


async def test_signup_rejects_duplicates_and_weak_passwords(client: AsyncClient) -> None:
    first = await register_doctor(client)
    email, phone = first["user"]["email"], first["user"]["phone"]
    assert (await client.post("/api/v1/auth/register/doctor", json=_registration(email=email))).status_code == 409
    assert (await client.post("/api/v1/auth/register/doctor", json=_registration(phone=phone))).status_code == 409
    assert (await client.post("/api/v1/auth/register/doctor", json=_registration(password="short"))).status_code == 422
    # A licence number is required: it's what the admin checks.
    assert (await client.post("/api/v1/auth/register/doctor", json=_registration(license_number=""))).status_code == 422


async def test_new_doctor_is_invisible_and_cannot_practise(client: AsyncClient, admin_client: AsyncClient) -> None:
    body = await register_doctor(client)
    doctor_id = body["doctor"]["id"]
    specialty = body["doctor"]["specialty"]

    search = (await client.get(f"/api/v1/doctors/search?specialty={specialty}")).json()
    assert doctor_id not in [row["doctor"]["id"] for row in search["items"]]

    clinic = await make_clinic(admin_client)
    start = datetime.now(timezone.utc) + timedelta(days=2)
    slot = await admin_client.post(
        "/api/v1/availability",
        json={
            "doctor_id": doctor_id, "clinic_id": clinic["id"],
            "start_time": start.isoformat(), "end_time": (start + timedelta(minutes=30)).isoformat(),
        },
    )
    assert slot.status_code == 403
    assert slot.json()["error"]["code"] == "doctor_not_verified"


async def test_verified_doctor_can_be_booked_again(client: AsyncClient, admin_client: AsyncClient) -> None:
    """The gate is the verification status, not the account: approving opens everything."""
    doctor = await ready_to_submit(client)
    doctor_id = doctor["doctor"]["id"]
    await client.post(f"/api/v1/doctors/{doctor_id}/submit", headers=doctor["headers"])
    approve = await admin_client.post(f"/api/v1/doctors/{doctor_id}/verification", json={"status": "verified"})
    assert approve.status_code == 200

    clinic = await make_clinic(admin_client)
    slot = await make_availability(admin_client, doctor_id, clinic["id"])
    patient = await register_patient(client)
    booking = await client.post(
        "/api/v1/appointments",
        headers=patient["headers"],
        json={
            "patient_id": patient["patient"]["id"], "doctor_id": doctor_id, "clinic_id": clinic["id"],
            "availability_id": slot["id"], "scheduled_start": slot["start_time"], "scheduled_end": slot["end_time"],
        },
    )
    assert booking.status_code == 201, booking.text


async def test_booking_an_unverified_doctor_is_refused(client: AsyncClient, admin_client: AsyncClient) -> None:
    doctor = await make_doctor(admin_client)  # verified by the factory
    clinic = await make_clinic(admin_client)
    slot = await make_availability(admin_client, doctor["id"], clinic["id"])
    # Verification withdrawn after the slot was published.
    await admin_client.patch(f"/api/v1/doctors/{doctor['id']}", json={"verification_status": "pending"})

    patient = await register_patient(client)
    booking = await client.post(
        "/api/v1/appointments",
        headers=patient["headers"],
        json={
            "patient_id": patient["patient"]["id"], "doctor_id": doctor["id"], "clinic_id": clinic["id"],
            "availability_id": slot["id"], "scheduled_start": slot["start_time"], "scheduled_end": slot["end_time"],
        },
    )
    assert booking.status_code == 403 and booking.json()["error"]["code"] == "doctor_not_verified"


# --- Documents ----------------------------------------------------------------------------


async def test_upload_list_download_and_delete(client: AsyncClient, admin_client: AsyncClient) -> None:
    doctor = await register_doctor(client)
    doctor_id = doctor["doctor"]["id"]
    created = await upload(client, doctor, "medical_license", name="my licence.pdf")
    assert created.status_code == 201, created.text
    document = created.json()
    assert document["content_type"] == "application/pdf"
    assert document["size_bytes"] == len(PDF)
    assert document["status"] == "pending"

    listed = (await client.get(f"/api/v1/doctors/{doctor_id}/documents", headers=doctor["headers"])).json()
    assert [d["id"] for d in listed] == [document["id"]]

    downloaded = await client.get(
        f"/api/v1/doctors/{doctor_id}/documents/{document['id']}/file", headers=doctor["headers"]
    )
    assert downloaded.status_code == 200
    assert downloaded.content == PDF
    # Always an attachment, never rendered in the browser.
    assert "attachment" in downloaded.headers["content-disposition"]

    # Admins can read it too (that's the point of the review queue).
    assert (await admin_client.get(f"/api/v1/doctors/{doctor_id}/documents/{document['id']}/file")).status_code == 200

    async with AsyncSessionLocal() as db:
        stored = await db.get(DoctorDocument, uuid.UUID(document["id"]))
        path = files.resolve(stored.stored_path)
    assert path.is_file()
    # The stored name is random: it never reuses what was uploaded.
    assert "licence" not in path.name

    deleted = await client.delete(
        f"/api/v1/doctors/{doctor_id}/documents/{document['id']}", headers=doctor["headers"]
    )
    assert deleted.status_code == 204
    assert not path.exists()


async def test_uploads_are_checked_by_content_not_by_name(client: AsyncClient) -> None:
    doctor = await register_doctor(client)
    disguised = await upload(client, doctor, "medical_license", name="licence.pdf", content=b"<?php evil();", content_type="application/pdf")
    assert disguised.status_code == 422
    assert "Unsupported file type" in disguised.json()["error"]["message"]
    assert (await upload(client, doctor, "medical_license", content=b"")).status_code == 422


async def test_upload_size_limit(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import config

    settings = config.get_settings()
    monkeypatch.setattr(settings, "max_upload_mb", 0.001, raising=False)  # ~1 KB
    doctor = await register_doctor(client)
    too_big = await upload(client, doctor, "medical_license", content=b"%PDF-1.4\n" + b"z" * 5000)
    assert too_big.status_code == 422
    assert "larger than" in too_big.json()["error"]["message"]


async def test_documents_are_private(client: AsyncClient) -> None:
    owner = await register_doctor(client)
    doctor_id = owner["doctor"]["id"]
    document = (await upload(client, owner, "medical_license")).json()
    stranger = await register_doctor(client)
    patient = await register_patient(client)

    for headers in (stranger["headers"], patient["headers"]):
        assert (await client.get(f"/api/v1/doctors/{doctor_id}/documents", headers=headers)).status_code == 404
        assert (
            await client.get(f"/api/v1/doctors/{doctor_id}/documents/{document['id']}/file", headers=headers)
        ).status_code == 404
    assert (await client.get(f"/api/v1/doctors/{doctor_id}/documents")).status_code == 401
    # Another doctor can't attach documents to someone else's application.
    assert (
        await client.post(
            f"/api/v1/doctors/{doctor_id}/documents",
            headers=stranger["headers"],
            data={"document_type": "national_id"},
            files=_file(),
        )
    ).status_code == 404


# --- Submitting and reviewing ---------------------------------------------------------------


async def test_submitting_needs_a_licence_and_an_id(client: AsyncClient) -> None:
    doctor = await register_doctor(client)
    doctor_id = doctor["doctor"]["id"]
    too_early = await client.post(f"/api/v1/doctors/{doctor_id}/submit", headers=doctor["headers"])
    assert too_early.status_code == 422 and too_early.json()["error"]["code"] == "missing_documents"

    await upload(client, doctor, "medical_license")
    still = await client.post(f"/api/v1/doctors/{doctor_id}/submit", headers=doctor["headers"])
    assert still.status_code == 422

    await upload(client, doctor, "national_id", name="id.png", content=PNG, content_type="image/png")
    submitted = await client.post(f"/api/v1/doctors/{doctor_id}/submit", headers=doctor["headers"])
    assert submitted.status_code == 200 and submitted.json()["submitted_at"] is not None

    again = await client.post(f"/api/v1/doctors/{doctor_id}/submit", headers=doctor["headers"])
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_submitted"


async def test_admin_sees_the_queue_and_approves(client: AsyncClient, admin_client: AsyncClient) -> None:
    doctor = await ready_to_submit(client)
    doctor_id = doctor["doctor"]["id"]
    await client.post(f"/api/v1/doctors/{doctor_id}/submit", headers=doctor["headers"])

    queue = (await admin_client.get("/api/v1/doctors/applications?page_size=100")).json()
    application = next(item for item in queue["items"] if item["doctor"]["id"] == doctor_id)
    assert {d["document_type"] for d in application["documents"]} == {"medical_license", "national_id"}

    marked = await admin_client.patch(
        f"/api/v1/doctors/{doctor_id}/documents/{application['documents'][0]['id']}",
        json={"status": "accepted", "review_notes": "Valid until 2030"},
    )
    assert marked.status_code == 200 and marked.json()["status"] == "accepted"

    approved = await admin_client.post(f"/api/v1/doctors/{doctor_id}/verification", json={"status": "verified"})
    assert approved.status_code == 200
    assert approved.json()["verification_status"] == "verified"
    assert approved.json()["reviewed_at"] is not None

    # The doctor sees the decision on their next session refresh.
    me = (await client.get("/api/v1/auth/me", headers=doctor["headers"])).json()
    assert me["doctor"]["verification_status"] == "verified"

    async with AsyncSessionLocal() as db:
        events = (
            await db.scalars(select(AuditEvent).where(AuditEvent.resource_id == uuid.UUID(doctor_id)))
        ).all()
    assert [e.action for e in events] == ["doctor.application_submitted", "doctor.verified"]
    assert events[-1].actor_type.value == "platform_admin"


async def test_rejection_explains_why_and_can_be_resubmitted(client: AsyncClient, admin_client: AsyncClient) -> None:
    doctor = await ready_to_submit(client)
    doctor_id = doctor["doctor"]["id"]
    await client.post(f"/api/v1/doctors/{doctor_id}/submit", headers=doctor["headers"])

    no_reason = await admin_client.post(f"/api/v1/doctors/{doctor_id}/verification", json={"status": "rejected"})
    assert no_reason.status_code == 422

    rejected = await admin_client.post(
        f"/api/v1/doctors/{doctor_id}/verification",
        json={"status": "rejected", "notes": "The licence photo is unreadable"},
    )
    assert rejected.status_code == 200
    body = rejected.json()
    assert body["verification_status"] == "rejected"
    assert body["verification_notes"] == "The licence photo is unreadable"
    # Out of the queue until they resubmit.
    assert body["submitted_at"] is None

    await upload(client, doctor, "medical_license", name="licence-2.pdf")
    resubmitted = await client.post(f"/api/v1/doctors/{doctor_id}/submit", headers=doctor["headers"])
    assert resubmitted.status_code == 200
    assert resubmitted.json()["verification_status"] == "pending"
    # The old reason is cleared, so the doctor isn't shown a stale rejection.
    assert resubmitted.json()["verification_notes"] is None


async def test_only_admins_decide(client: AsyncClient, admin_client: AsyncClient) -> None:
    doctor = await ready_to_submit(client)
    doctor_id = doctor["doctor"]["id"]
    await client.post(f"/api/v1/doctors/{doctor_id}/submit", headers=doctor["headers"])

    # A doctor can't verify themself, through the decision endpoint or the profile.
    assert (
        await client.post(
            f"/api/v1/doctors/{doctor_id}/verification", headers=doctor["headers"], json={"status": "verified"}
        )
    ).status_code == 403
    assert (
        await client.patch(
            f"/api/v1/doctors/{doctor_id}", headers=doctor["headers"], json={"verification_status": "verified"}
        )
    ).status_code == 403
    assert (await client.get("/api/v1/doctors/applications", headers=doctor["headers"])).status_code == 403

    patient = await register_patient(client)
    assert (
        await client.post(
            f"/api/v1/doctors/{doctor_id}/verification", headers=patient["headers"], json={"status": "verified"}
        )
    ).status_code == 403

    # But they can still edit their own profile while waiting.
    assert (
        await client.patch(f"/api/v1/doctors/{doctor_id}", headers=doctor["headers"], json={"bio": "10 years in laser"})
    ).status_code == 200


async def test_review_endpoint_needs_a_submitted_application(client: AsyncClient, admin_client: AsyncClient) -> None:
    doctor = await register_doctor(client)
    decision = await admin_client.post(
        f"/api/v1/doctors/{doctor['doctor']['id']}/verification", json={"status": "verified"}
    )
    assert decision.status_code == 409
