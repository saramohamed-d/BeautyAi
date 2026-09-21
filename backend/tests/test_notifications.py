"""Sprint 15: notifications — confirmations, reminders, aftercare, receipts, decisions, and sending them."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.enums import Language, NotificationChannel, NotificationStatus
from app.models.notification import Notification
from app.models.patient import Patient
from app.notifications.providers import (
    DemoNotifier,
    Message,
    NotificationError,
    TwilioNotifier,
    get_notifier,
)
from app.notifications.templates import render
from app.services import notification_service
from tests.factories import make_availability, make_clinic, make_doctor, register_patient
from tests.test_doctor_verification import PNG, register_doctor, upload
from tests.test_payments import _demo_event


async def _notifications(**filters) -> list[Notification]:
    async with AsyncSessionLocal() as db:
        query = select(Notification)
        for field, value in filters.items():
            query = query.where(getattr(Notification, field) == value)
        rows = await db.scalars(query.order_by(Notification.scheduled_for))
        return list(rows.all())


async def _book(client: AsyncClient, admin_client: AsyncClient, *, hours_ahead: float = 72, **patient_kwargs) -> dict:
    doctor = await make_doctor(admin_client)
    clinic = await make_clinic(admin_client, phone="+20223456789")
    start = datetime.now(timezone.utc) + timedelta(hours=hours_ahead)
    slot = await make_availability(
        admin_client,
        doctor["id"],
        clinic["id"],
        start_time=start.isoformat(),
        end_time=(start + timedelta(minutes=30)).isoformat(),
    )
    patient = await register_patient(client, **patient_kwargs)
    booking = await client.post(
        "/api/v1/appointments",
        headers=patient["headers"],
        json={
            "patient_id": patient["patient"]["id"], "doctor_id": doctor["id"], "clinic_id": clinic["id"],
            "availability_id": slot["id"], "scheduled_start": slot["start_time"], "scheduled_end": slot["end_time"],
        },
    )
    assert booking.status_code == 201, booking.text
    return {"patient": patient, "doctor": doctor, "clinic": clinic, "appointment": booking.json(), "slot": slot}


# --- Templates ------------------------------------------------------------------------------


def test_templates_render_in_both_languages() -> None:
    context = {
        "patient_name": "Nour", "doctor_name": "Dr Amira", "clinic_name": "New Look", "when": "Sunday 3:00 PM",
        "address_line": "26 July St", "appointments_url": "https://app/appointments",
    }
    english = render("appointment_reminder", Language.EN, NotificationChannel.EMAIL, context)
    arabic = render("appointment_reminder", Language.AR, NotificationChannel.EMAIL, context)
    assert "Dr Amira" in english.body and english.subject and "Tomorrow" in english.subject
    assert "تذكير" in (arabic.subject or "") and "Dr Amira" in arabic.body

    # SMS gets its own short wording, and no subject.
    sms = render("appointment_reminder", Language.EN, NotificationChannel.SMS, context)
    assert sms.subject is None
    assert len(sms.body) < len(english.body)

    with pytest.raises(KeyError):
        render("no_such_template", Language.EN, NotificationChannel.EMAIL, context)
    # A missing placeholder is a loud failure, not "Hi {patient_name}".
    with pytest.raises(KeyError):
        render("appointment_reminder", Language.EN, NotificationChannel.EMAIL, {"patient_name": "Nour"})


# --- Booking writes the messages ---------------------------------------------------------------


async def test_booking_schedules_confirmation_reminder_and_aftercare(
    client: AsyncClient, admin_client: AsyncClient
) -> None:
    world = await _book(client, admin_client)
    appointment_id = uuid.UUID(world["appointment"]["id"])
    rows = await _notifications(appointment_id=appointment_id)

    by_template = {row.template for row in rows}
    assert by_template == {"appointment_confirmed", "appointment_reminder", "aftercare_followup"}
    # The patient signed up with email and phone; SMS is on by default, WhatsApp isn't.
    assert {row.channel for row in rows} == {NotificationChannel.EMAIL, NotificationChannel.SMS}
    assert all(row.status == NotificationStatus.PENDING for row in rows)

    start = datetime.fromisoformat(world["appointment"]["scheduled_start"])
    reminder = next(row for row in rows if row.template == "appointment_reminder")
    aftercare = next(row for row in rows if row.template == "aftercare_followup")
    confirmation = next(row for row in rows if row.template == "appointment_confirmed")
    assert confirmation.scheduled_for <= datetime.now(timezone.utc) + timedelta(seconds=5)
    assert reminder.scheduled_for == start - timedelta(hours=24)
    assert aftercare.scheduled_for > start

    # The message says what it's about, in the patient's language.
    assert world["doctor"]["full_name"] in confirmation.body
    assert world["clinic"]["name"] in confirmation.body


async def test_a_booking_for_today_gets_no_tomorrow_reminder(client: AsyncClient, admin_client: AsyncClient) -> None:
    world = await _book(client, admin_client, hours_ahead=3)
    rows = await _notifications(appointment_id=uuid.UUID(world["appointment"]["id"]))
    assert "appointment_reminder" not in {row.template for row in rows}
    assert "aftercare_followup" in {row.template for row in rows}


async def test_arabic_patients_get_arabic_messages(client: AsyncClient, admin_client: AsyncClient) -> None:
    world = await _book(client, admin_client, preferred_language="ar")
    rows = await _notifications(appointment_id=uuid.UUID(world["appointment"]["id"]))
    confirmation = next(row for row in rows if row.template == "appointment_confirmed")
    assert confirmation.language == Language.AR
    assert "تم حجز موعدك" in (confirmation.subject or "")


async def test_channel_preferences_are_respected(client: AsyncClient, admin_client: AsyncClient) -> None:
    patient = await register_patient(client)
    turned_off = await client.patch(
        f"/api/v1/patients/{patient['patient']['id']}",
        headers=patient["headers"],
        json={"notify_sms": False, "notify_whatsapp": True},
    )
    assert turned_off.status_code == 200
    assert turned_off.json()["notify_sms"] is False

    doctor = await make_doctor(admin_client)
    clinic = await make_clinic(admin_client)
    slot = await make_availability(admin_client, doctor["id"], clinic["id"])
    booking = await client.post(
        "/api/v1/appointments",
        headers=patient["headers"],
        json={
            "patient_id": patient["patient"]["id"], "doctor_id": doctor["id"], "clinic_id": clinic["id"],
            "availability_id": slot["id"], "scheduled_start": slot["start_time"], "scheduled_end": slot["end_time"],
        },
    )
    rows = await _notifications(appointment_id=uuid.UUID(booking.json()["id"]))
    channels = {row.channel for row in rows}
    assert NotificationChannel.SMS not in channels
    assert {NotificationChannel.EMAIL, NotificationChannel.WHATSAPP} == channels


async def test_a_patient_without_email_still_gets_sms_and_a_visible_skip(
    client: AsyncClient, admin_client: AsyncClient
) -> None:
    world = await _book(client, admin_client)
    patient_id = uuid.UUID(world["patient"]["patient"]["id"])
    async with AsyncSessionLocal() as db:
        await db.execute(update(Patient).where(Patient.id == patient_id).values(email=None))
        await db.commit()

    doctor, clinic = world["doctor"], world["clinic"]
    start = datetime.now(timezone.utc) + timedelta(days=4)
    slot = await make_availability(
        admin_client, doctor["id"], clinic["id"],
        start_time=start.isoformat(), end_time=(start + timedelta(minutes=30)).isoformat(),
    )
    booking = await client.post(
        "/api/v1/appointments",
        headers=world["patient"]["headers"],
        json={
            "patient_id": str(patient_id), "doctor_id": doctor["id"], "clinic_id": clinic["id"],
            "availability_id": slot["id"], "scheduled_start": slot["start_time"], "scheduled_end": slot["end_time"],
        },
    )
    rows = await _notifications(appointment_id=uuid.UUID(booking.json()["id"]))
    email = next(row for row in rows if row.channel == NotificationChannel.EMAIL)
    assert email.status == NotificationStatus.SKIPPED
    assert email.error == "No address for this channel"
    assert any(row.channel == NotificationChannel.SMS and row.status == NotificationStatus.PENDING for row in rows)


# --- Cancelling ------------------------------------------------------------------------------


async def test_cancelling_stops_the_reminder_and_tells_the_patient(
    client: AsyncClient, admin_client: AsyncClient
) -> None:
    world = await _book(client, admin_client)
    appointment_id = uuid.UUID(world["appointment"]["id"])
    cancelled = await admin_client.patch(
        f"/api/v1/appointments/{appointment_id}", json={"status": "cancelled"}
    )
    assert cancelled.status_code == 200

    rows = await _notifications(appointment_id=appointment_id)
    by_template = {}
    for row in rows:
        by_template.setdefault(row.template, []).append(row)
    assert all(row.status == NotificationStatus.CANCELLED for row in by_template["appointment_reminder"])
    assert all(row.status == NotificationStatus.CANCELLED for row in by_template["aftercare_followup"])
    assert all(row.status == NotificationStatus.PENDING for row in by_template["appointment_cancelled"])
    # The confirmation already went out (or is due now); it isn't retracted.
    assert all(row.status == NotificationStatus.PENDING for row in by_template["appointment_confirmed"])


async def test_a_refunded_cancellation_says_so(client: AsyncClient, admin_client: AsyncClient) -> None:
    doctor = await make_doctor(admin_client)
    clinic = await make_clinic(admin_client)
    await admin_client.put(
        f"/api/v1/clinics/{clinic['id']}/doctors/{doctor['id']}/fee", json={"consultation_fee": 500}
    )
    slot = await make_availability(admin_client, doctor["id"], clinic["id"])
    patient = await register_patient(client)
    checkout = await client.post(
        "/api/v1/payments/checkout",
        headers=patient["headers"],
        json={"availability_id": slot["id"], "method": "card", "idempotency_key": str(uuid.uuid4())},
    )
    payment_id = checkout.json()["payment"]["id"]
    await _demo_event(client, payment_id, "paid")
    appointment_id = (await client.get(f"/api/v1/payments/{payment_id}", headers=patient["headers"])).json()[
        "appointment_id"
    ]

    # The receipt was written when the money arrived.
    receipts = [row for row in await _notifications(appointment_id=uuid.UUID(appointment_id)) if row.template == "payment_receipt"]
    assert receipts, "a receipt should be written for a paid booking"
    assert "500.00 EGP" in receipts[0].body

    await admin_client.patch(f"/api/v1/appointments/{appointment_id}", json={"status": "cancelled"})
    cancelled = [
        row for row in await _notifications(appointment_id=uuid.UUID(appointment_id))
        if row.template == "appointment_cancelled"
    ]
    assert cancelled and "refunded in full" in cancelled[0].body


# --- Doctor decisions --------------------------------------------------------------------------


async def test_doctors_are_told_about_the_decision(client: AsyncClient, admin_client: AsyncClient) -> None:
    doctor = await register_doctor(client)
    doctor_id = doctor["doctor"]["id"]
    await upload(client, doctor, "medical_license")
    await upload(client, doctor, "national_id", name="id.png", content=PNG, content_type="image/png")
    await client.post(f"/api/v1/doctors/{doctor_id}/submit", headers=doctor["headers"])

    await admin_client.post(
        f"/api/v1/doctors/{doctor_id}/verification", json={"status": "rejected", "notes": "Licence unreadable"}
    )
    rejected = [row for row in await _notifications(user_id=uuid.UUID(doctor["user"]["id"]))]
    assert any(row.template == "doctor_rejected" and "Licence unreadable" in row.body for row in rejected)

    await client.post(f"/api/v1/doctors/{doctor_id}/submit", headers=doctor["headers"])
    await admin_client.post(f"/api/v1/doctors/{doctor_id}/verification", json={"status": "verified"})
    after = await _notifications(user_id=uuid.UUID(doctor["user"]["id"]))
    assert any(row.template == "doctor_verified" for row in after)


# --- Sending ------------------------------------------------------------------------------


async def test_dispatch_sends_what_is_due_and_nothing_else(client: AsyncClient, admin_client: AsyncClient) -> None:
    world = await _book(client, admin_client)
    appointment_id = uuid.UUID(world["appointment"]["id"])

    # Other tests leave messages behind, so drain rather than count globally.
    for _ in range(5):
        if (await admin_client.post("/api/v1/admin/notifications/dispatch")).json()["sent"] == 0:
            break

    rows = await _notifications(appointment_id=appointment_id)
    confirmations = [row for row in rows if row.template == "appointment_confirmed"]
    assert confirmations
    assert all(row.status == NotificationStatus.SENT for row in confirmations)
    assert all(row.sent_at is not None and row.provider == "demo" for row in confirmations)
    assert all(row.provider_message_id for row in confirmations)
    # Tomorrow's reminder is untouched.
    assert all(
        row.status == NotificationStatus.PENDING for row in rows if row.template == "appointment_reminder"
    )

    # Running it again doesn't send the same message a second time.
    sent_at = {row.id: row.sent_at for row in confirmations}
    await admin_client.post("/api/v1/admin/notifications/dispatch")
    after = {
        row.id: row.sent_at
        for row in await _notifications(appointment_id=appointment_id)
        if row.template == "appointment_confirmed"
    }
    assert after == sent_at


async def test_the_reminder_goes_out_when_its_time_comes(client: AsyncClient, admin_client: AsyncClient) -> None:
    world = await _book(client, admin_client)
    appointment_id = uuid.UUID(world["appointment"]["id"])

    async with AsyncSessionLocal() as db:
        # Pretend it's the day before the appointment.
        await db.execute(
            update(Notification)
            .where(Notification.appointment_id == appointment_id, Notification.template == "appointment_reminder")
            .values(scheduled_for=datetime.now(timezone.utc) - timedelta(minutes=1))
        )
        await db.commit()

    await admin_client.post("/api/v1/admin/notifications/dispatch")
    rows = await _notifications(appointment_id=appointment_id)
    reminders = [row for row in rows if row.template == "appointment_reminder"]
    assert reminders and all(row.status == NotificationStatus.SENT for row in reminders)


async def test_failures_are_retried_then_marked_failed(client: AsyncClient, admin_client: AsyncClient) -> None:
    class Broken(DemoNotifier):
        async def send(self, message: Message):
            raise NotificationError("Mailbox full")

    app.dependency_overrides[get_notifier] = Broken
    try:
        world = await _book(client, admin_client)
        appointment_id = uuid.UUID(world["appointment"]["id"])
        for _ in range(notification_service.MAX_ATTEMPTS):
            await admin_client.post("/api/v1/admin/notifications/dispatch")
        rows = [
            row for row in await _notifications(appointment_id=appointment_id)
            if row.template == "appointment_confirmed"
        ]
        assert all(row.status == NotificationStatus.FAILED for row in rows)
        assert all(row.attempts == notification_service.MAX_ATTEMPTS for row in rows)
        assert all(row.error == "Mailbox full" for row in rows)

        # Out of attempts: later runs leave it alone rather than looping forever.
        result = (await admin_client.post("/api/v1/admin/notifications/dispatch")).json()
        assert result["failed"] == 0
    finally:
        app.dependency_overrides.pop(get_notifier, None)


async def test_admins_can_read_the_message_history(client: AsyncClient, admin_client: AsyncClient) -> None:
    await _book(client, admin_client)
    listed = (await admin_client.get("/api/v1/admin/notifications?page_size=100")).json()
    assert listed["total"] >= 3
    assert {"template", "channel", "status", "body"} <= set(listed["items"][0])

    by_channel = (await admin_client.get("/api/v1/admin/notifications?channel=sms&page_size=100")).json()
    assert all(item["channel"] == "sms" for item in by_channel["items"])


async def test_notification_endpoints_are_admin_only(client: AsyncClient) -> None:
    patient = await register_patient(client)
    assert (await client.get("/api/v1/admin/notifications", headers=patient["headers"])).status_code == 403
    assert (await client.post("/api/v1/admin/notifications/dispatch", headers=patient["headers"])).status_code == 403
    assert (await client.get("/api/v1/admin/notifications")).status_code == 401


# --- Providers ------------------------------------------------------------------------------


async def test_twilio_sends_sms_and_whatsapp() -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            {"url": str(request.url), "auth": request.headers.get("authorization", ""), "body": request.content.decode()}
        )
        return httpx.Response(201, json={"sid": "SM123"})

    notifier = TwilioNotifier(transport=httpx.MockTransport(handler))
    notifier.settings = notifier.settings.model_copy(
        update={
            "twilio_account_sid": "AC123", "twilio_auth_token": "secret",
            "twilio_sms_from": "+15550001111", "twilio_whatsapp_from": "+15550002222",
        }
    )

    sms = await notifier.send(
        Message(channel=NotificationChannel.SMS, recipient="+201555001122", subject=None, body="Reminder")
    )
    assert sms.provider == "twilio" and sms.message_id == "SM123"
    assert "/2010-04-01/Accounts/AC123/Messages.json" in seen[0]["url"]
    assert seen[0]["auth"].startswith("Basic ")
    assert "From=%2B15550001111" in seen[0]["body"] and "To=%2B201555001122" in seen[0]["body"]

    await notifier.send(
        Message(channel=NotificationChannel.WHATSAPP, recipient="+201555001122", subject=None, body="Reminder")
    )
    # WhatsApp uses the same endpoint with both numbers prefixed.
    assert "From=whatsapp%3A%2B15550002222" in seen[1]["body"]
    assert "To=whatsapp%3A%2B201555001122" in seen[1]["body"]


async def test_twilio_reports_rejections_and_misconfiguration() -> None:
    notifier = TwilioNotifier(transport=httpx.MockTransport(lambda request: httpx.Response(400, json={"message": "bad"})))
    notifier.settings = notifier.settings.model_copy(
        update={"twilio_account_sid": "AC123", "twilio_auth_token": "secret", "twilio_sms_from": "+15550001111"}
    )
    with pytest.raises(NotificationError):
        await notifier.send(Message(channel=NotificationChannel.SMS, recipient="+20100", subject=None, body="x"))

    # WhatsApp isn't configured on this account.
    assert notifier.supports(NotificationChannel.WHATSAPP) is False
    with pytest.raises(NotificationError):
        await notifier.send(Message(channel=NotificationChannel.WHATSAPP, recipient="+20100", subject=None, body="x"))


async def test_the_money_amount_is_formatted_for_a_receipt() -> None:
    body = render(
        "payment_receipt",
        Language.EN,
        NotificationChannel.SMS,
        {
            "patient_name": "Nour", "doctor_name": "Dr Amira", "clinic_name": "New Look", "when": "Sunday",
            "amount": f"{Decimal('500.00'):.2f} EGP", "reference": "ABC123",
        },
    ).body
    assert "500.00 EGP" in body and "ABC123" in body
