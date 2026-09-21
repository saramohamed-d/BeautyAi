"""Sprint 17: password reset, contact verification, rate limiting, security headers, and data rights."""

import uuid
from datetime import datetime, timedelta, timezone

from httpx import AsyncClient
from sqlalchemy import select, update

from app.core import rate_limit
from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.auth_token import AuthToken
from app.models.audit import AuditEvent
from app.models.conversation import Conversation
from app.models.enums import AuthTokenPurpose
from app.models.notification import Notification
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.scheduling import Appointment
from app.models.user import RefreshToken, User
from tests.factories import (
    TEST_PASSWORD,
    make_availability,
    make_clinic,
    make_doctor,
    register_patient,
)

NEW_PASSWORD = "a-brand-new-passphrase"


async def _token_for(user_id: str, purpose: AuthTokenPurpose) -> AuthToken | None:
    async with AsyncSessionLocal() as db:
        return await db.scalar(
            select(AuthToken)
            .where(AuthToken.user_id == uuid.UUID(user_id), AuthToken.purpose == purpose)
            .order_by(AuthToken.created_at.desc())
        )


async def _message_body(user_id: str, template: str) -> str | None:
    """The notification the platform wrote — where the reset link and code live."""
    async with AsyncSessionLocal() as db:
        row = await db.scalar(
            select(Notification)
            .where(Notification.user_id == uuid.UUID(user_id), Notification.template == template)
            .order_by(Notification.created_at.desc())
        )
    return row.body if row else None


def _link_token(body: str) -> str:
    return body.split("token=")[1].split()[0].strip()


# --- Password reset --------------------------------------------------------------------------


async def test_password_reset_end_to_end(client: AsyncClient) -> None:
    patient = await register_patient(client)
    email = patient["user"]["email"]

    asked = await client.post("/api/v1/auth/password/forgot", json={"identifier": email})
    assert asked.status_code == 200
    body = await _message_body(patient["user"]["id"], "password_reset")
    assert body and "reset-password?token=" in body

    token = _link_token(body)
    reset = await client.post("/api/v1/auth/password/reset", json={"token": token, "password": NEW_PASSWORD})
    assert reset.status_code == 200

    # The new password works, the old one doesn't.
    assert (
        await client.post("/api/v1/auth/login", json={"identifier": email, "password": NEW_PASSWORD})
    ).status_code == 200
    assert (
        await client.post("/api/v1/auth/login", json={"identifier": email, "password": TEST_PASSWORD})
    ).status_code == 401


async def test_a_reset_link_works_once(client: AsyncClient) -> None:
    patient = await register_patient(client)
    await client.post("/api/v1/auth/password/forgot", json={"identifier": patient["user"]["email"]})
    token = _link_token(await _message_body(patient["user"]["id"], "password_reset"))

    assert (
        await client.post("/api/v1/auth/password/reset", json={"token": token, "password": NEW_PASSWORD})
    ).status_code == 200
    again = await client.post("/api/v1/auth/password/reset", json={"token": token, "password": "yet-another-one"})
    assert again.status_code == 401 and again.json()["error"]["code"] == "invalid_token"


async def test_asking_again_invalidates_the_older_link(client: AsyncClient) -> None:
    patient = await register_patient(client)
    email = patient["user"]["email"]
    await client.post("/api/v1/auth/password/forgot", json={"identifier": email})
    first = _link_token(await _message_body(patient["user"]["id"], "password_reset"))
    await client.post("/api/v1/auth/password/forgot", json={"identifier": email})
    second = _link_token(await _message_body(patient["user"]["id"], "password_reset"))
    assert first != second

    stale = await client.post("/api/v1/auth/password/reset", json={"token": first, "password": NEW_PASSWORD})
    assert stale.status_code == 401
    assert (
        await client.post("/api/v1/auth/password/reset", json={"token": second, "password": NEW_PASSWORD})
    ).status_code == 200


async def test_an_expired_link_is_refused(client: AsyncClient) -> None:
    patient = await register_patient(client)
    await client.post("/api/v1/auth/password/forgot", json={"identifier": patient["user"]["email"]})
    token = _link_token(await _message_body(patient["user"]["id"], "password_reset"))

    async with AsyncSessionLocal() as db:
        await db.execute(
            update(AuthToken)
            .where(AuthToken.user_id == uuid.UUID(patient["user"]["id"]))
            .values(expires_at=datetime.now(timezone.utc) - timedelta(minutes=1))
        )
        await db.commit()

    late = await client.post("/api/v1/auth/password/reset", json={"token": token, "password": NEW_PASSWORD})
    assert late.status_code == 401


async def test_resetting_ends_every_open_session(client: AsyncClient) -> None:
    """If the reset was needed because someone else had the account, their sessions must die too."""
    patient = await register_patient(client)
    await client.post("/api/v1/auth/password/forgot", json={"identifier": patient["user"]["email"]})
    token = _link_token(await _message_body(patient["user"]["id"], "password_reset"))
    await client.post("/api/v1/auth/password/reset", json={"token": token, "password": NEW_PASSWORD})

    async with AsyncSessionLocal() as db:
        sessions = (
            await db.scalars(select(RefreshToken).where(RefreshToken.user_id == uuid.UUID(patient["user"]["id"])))
        ).all()
    assert sessions and all(session.revoked_at is not None for session in sessions)


async def test_forgot_password_says_nothing_about_who_has_an_account(client: AsyncClient) -> None:
    known = await register_patient(client)
    for identifier in (known["user"]["email"], "nobody-here@example.com", "+201000000000"):
        response = await client.post("/api/v1/auth/password/forgot", json={"identifier": identifier})
        assert response.status_code == 200
        assert response.json()["message"] == "If that account exists, we've sent it instructions."

    # And nothing was written for the address that doesn't exist.
    async with AsyncSessionLocal() as db:
        stray = await db.scalar(
            select(Notification).where(Notification.recipient == "nobody-here@example.com")
        )
    assert stray is None


# --- Verifying an email address ------------------------------------------------------------


async def test_verifying_an_email_address(client: AsyncClient) -> None:
    patient = await register_patient(client)
    me = (await client.get("/api/v1/auth/me", headers=patient["headers"])).json()
    assert me["user"]["email_verified_at"] is None

    asked = await client.post("/api/v1/auth/verify/request", headers=patient["headers"], json={"channel": "email"})
    assert asked.status_code == 200
    body = await _message_body(patient["user"]["id"], "verify_contact")
    code = "".join(character for character in body if character.isdigit())[:6]

    wrong = await client.post(
        "/api/v1/auth/verify/confirm", headers=patient["headers"], json={"channel": "email", "code": "000000"}
    )
    assert wrong.status_code == 401

    confirmed = await client.post(
        "/api/v1/auth/verify/confirm", headers=patient["headers"], json={"channel": "email", "code": code}
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["user"]["email_verified_at"] is not None

    # The code is spent.
    assert (
        await client.post(
            "/api/v1/auth/verify/confirm", headers=patient["headers"], json={"channel": "email", "code": code}
        )
    ).status_code in (401, 409)


async def test_codes_stop_working_after_too_many_guesses(client: AsyncClient) -> None:
    patient = await register_patient(client)
    await client.post("/api/v1/auth/verify/request", headers=patient["headers"], json={"channel": "email"})
    body = await _message_body(patient["user"]["id"], "verify_contact")
    code = "".join(character for character in body if character.isdigit())[:6]

    for _ in range(5):
        await client.post(
            "/api/v1/auth/verify/confirm", headers=patient["headers"], json={"channel": "email", "code": "111111"}
        )
    # Even the right code is refused now: a new one must be requested.
    blocked = await client.post(
        "/api/v1/auth/verify/confirm", headers=patient["headers"], json={"channel": "email", "code": code}
    )
    assert blocked.status_code == 401


async def test_verification_needs_a_session(client: AsyncClient) -> None:
    assert (await client.post("/api/v1/auth/verify/request", json={"channel": "email"})).status_code == 401


# --- Data rights (PDPL) ----------------------------------------------------------------------


async def _booked_patient(client: AsyncClient, admin_client: AsyncClient) -> dict:
    doctor = await make_doctor(admin_client)
    clinic = await make_clinic(admin_client)
    slot = await make_availability(admin_client, doctor["id"], clinic["id"])
    patient = await register_patient(client)
    booking = await client.post(
        "/api/v1/appointments",
        headers=patient["headers"],
        json={
            "patient_id": patient["patient"]["id"], "doctor_id": doctor["id"], "clinic_id": clinic["id"],
            "availability_id": slot["id"], "scheduled_start": slot["start_time"], "scheduled_end": slot["end_time"],
        },
    )
    assert booking.status_code == 201
    await client.post("/api/v1/conversations", headers=patient["headers"], json={"accept_ai_terms": True})
    return patient


async def test_a_patient_can_export_everything_held_about_them(
    client: AsyncClient, admin_client: AsyncClient
) -> None:
    patient = await _booked_patient(client, admin_client)
    export = await client.get("/api/v1/auth/me/data", headers=patient["headers"])
    assert export.status_code == 200
    data = export.json()

    assert data["account"]["email"] == patient["user"]["email"]
    assert data["patient_profile"]["full_name"] == patient["patient"]["full_name"]
    assert len(data["appointments"]) == 1
    assert len(data["conversations"]) == 1
    assert data["messages_to_you"], "the reminders we sent are part of their record"
    # Secrets never leave, even to their owner.
    assert "password_hash" not in data["account"]
    assert all("password_hash" not in str(section) for section in data.values())

    assert (await client.get("/api/v1/auth/me/data")).status_code == 401


async def test_deleting_an_account_erases_the_person_but_keeps_the_records(
    client: AsyncClient, admin_client: AsyncClient
) -> None:
    patient = await _booked_patient(client, admin_client)
    patient_id = uuid.UUID(patient["patient"]["id"])
    user_id = uuid.UUID(patient["user"]["id"])

    wrong = await client.post("/api/v1/auth/me/delete", headers=patient["headers"], json={"password": "not-it"})
    assert wrong.status_code == 401

    deleted = await client.post(
        "/api/v1/auth/me/delete", headers=patient["headers"], json={"password": TEST_PASSWORD}
    )
    assert deleted.status_code == 200
    assert deleted.json()["kept"]["appointments"] == 1

    async with AsyncSessionLocal() as db:
        assert await db.get(User, user_id) is None
        profile = await db.get(Patient, patient_id)
        # The profile stays attached to the appointment, with nothing personal on it.
        assert profile is not None
        assert profile.full_name == "Deleted patient"
        assert profile.email is None and profile.user_id is None
        assert patient["patient"]["phone"] not in profile.phone

        appointments = (await db.scalars(select(Appointment).where(Appointment.patient_id == patient_id))).all()
        assert len(appointments) == 1
        # Their own words are deleted outright.
        conversations = (await db.scalars(select(Conversation).where(Conversation.patient_id == patient_id))).all()
        assert conversations == []
        messages = (await db.scalars(select(Notification).where(Notification.patient_id == patient_id))).all()
        assert messages == []
        # And the deletion itself is recorded.
        event = await db.scalar(select(AuditEvent).where(AuditEvent.resource_id == user_id))
        assert event is not None and event.action == "user.deleted"

    # The session is gone with the account.
    assert (await client.get("/api/v1/auth/me", headers=patient["headers"])).status_code == 401


async def test_payments_survive_deletion_for_the_books(client: AsyncClient, admin_client: AsyncClient) -> None:
    doctor = await make_doctor(admin_client)
    clinic = await make_clinic(admin_client)
    slot = await make_availability(admin_client, doctor["id"], clinic["id"])
    patient = await register_patient(client)
    checkout = await client.post(
        "/api/v1/payments/checkout",
        headers=patient["headers"],
        json={"availability_id": slot["id"], "method": "pay_at_clinic", "idempotency_key": str(uuid.uuid4())},
    )
    assert checkout.status_code == 200

    result = await client.post(
        "/api/v1/auth/me/delete", headers=patient["headers"], json={"password": TEST_PASSWORD}
    )
    assert result.json()["kept"]["payments"] == 1
    async with AsyncSessionLocal() as db:
        payments = (
            await db.scalars(select(Payment).where(Payment.patient_id == uuid.UUID(patient["patient"]["id"])))
        ).all()
    assert len(payments) == 1


# --- Rate limiting and headers ------------------------------------------------------------


async def test_repeated_password_guesses_are_throttled(client: AsyncClient) -> None:
    patient = await register_patient(client)
    email = patient["user"]["email"]

    # The limiter is off for the rest of the suite (see conftest); turn it
    # on for this test only, with clean counters.
    settings = get_settings()
    settings.rate_limit_enabled = True
    await rate_limit.reset()
    try:
        statuses = [
            (await client.post("/api/v1/auth/login", json={"identifier": email, "password": "wrong"})).status_code
            for _ in range(12)
        ]
        assert 429 in statuses, "guessing should be throttled"
        blocked = next(index for index, status in enumerate(statuses) if status == 429)
        assert blocked >= 8, f"throttled too early, after {blocked} attempts"

        # Guessing is throttled per account, not per address: everyone
        # behind one carrier NAT or one clinic's office line must not be
        # locked out because someone else typed their password wrong.
        other = await register_patient(client)
        assert (
            await client.post(
                "/api/v1/auth/login", json={"identifier": other["user"]["email"], "password": TEST_PASSWORD}
            )
        ).status_code == 200

        # The 429 tells a well-behaved client when to come back.
        response = await client.post("/api/v1/auth/login", json={"identifier": email, "password": "wrong"})
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "rate_limited"
        assert "Retry-After" in response.headers
    finally:
        settings.rate_limit_enabled = False
        await rate_limit.reset()


async def test_the_limiter_counts_per_bucket_and_window() -> None:
    """Unit-level: one bucket filling up doesn't affect another."""
    settings = get_settings()
    settings.rate_limit_enabled = True
    await rate_limit.reset()
    try:
        for _ in range(3):
            assert await rate_limit.hit("login", "1.2.3.4", times=3, seconds=60)
        assert not await rate_limit.hit("login", "1.2.3.4", times=3, seconds=60)
        # A different caller, and a different endpoint group, are unaffected.
        assert await rate_limit.hit("login", "5.6.7.8", times=3, seconds=60)
        assert await rate_limit.hit("register", "1.2.3.4", times=3, seconds=60)
    finally:
        settings.rate_limit_enabled = False
        await rate_limit.reset()


async def test_security_headers_are_on_every_response(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["Referrer-Policy"] == "no-referrer"
    # HSTS only where there is TLS to insist on.
    assert "Strict-Transport-Security" not in response.headers
