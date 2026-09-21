"""
Notifications: what to send, to whom, when (Sprint 15; docs/notifications.md).

Design decisions:

- **Messages are written to the database first, then sent.** Booking an
  appointment writes three rows: the confirmation (due now), the
  reminder (due the day before) and the aftercare follow-up (due the day
  after). A separate sender delivers whatever is due
  (`app/notifications/cli.py`, or the admin's "send due now" button).
  Nothing is sent from inside the request that caused it, so a slow or
  broken provider can never fail a booking or a payment.
- **`dedupe_key` carries the reason** ("reminder:<appointment id>"), and
  is unique. Re-running the booking code, retrying a webhook or running
  the sender twice can't produce a second message.
- **Cancelling the reason cancels the message.** A cancelled appointment
  marks its unsent reminder and follow-up `cancelled`; they are never
  deleted, so the history stays.
- **Preferences are respected at write time**, and a channel the patient
  turned off still gets a row with status `skipped` — "why didn't they
  get an SMS?" must be answerable.
- **Aftercare is deliberately not medical advice**: it points back to the
  clinic that did the work (see templates).
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.enums import Language, NotificationChannel, NotificationStatus
from app.models.notification import Notification
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.scheduling import Appointment
from app.models.user import User
from app.notifications import templates
from app.notifications.providers import Message, NotificationError, Notifier
from app.notifications.templates import render

logger = get_logger(__name__)

# A failed message is retried by the next run, up to this many times.
MAX_ATTEMPTS = 3
UNSENT = (NotificationStatus.PENDING,)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _tz() -> ZoneInfo:
    return ZoneInfo(get_settings().clinic_timezone)


def _local(moment: datetime, language: Language) -> str:
    """The appointment time as the patient would say it, in their language."""
    local = moment.astimezone(_tz())
    if language == Language.AR:
        days = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
        months = [
            "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
            "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
        ]
        hour = local.hour % 12 or 12
        part = "صباحاً" if local.hour < 12 else "مساءً"
        return f"{days[local.weekday()]} {local.day} {months[local.month - 1]} — {hour}:{local.minute:02d} {part}"
    return local.strftime("%A %-d %B, %-I:%M %p")


def channels_for(patient: Patient | None, *, email: str | None, phone: str | None) -> dict[NotificationChannel, str | None]:
    """
    Which channels to write for this recipient, and the address for each.

    A `None` address means "wanted, but we have nothing to send to" — the
    row is written as `skipped` so it's visible.
    """
    wants = {
        NotificationChannel.EMAIL: patient.notify_email if patient else True,
        NotificationChannel.SMS: patient.notify_sms if patient else False,
        NotificationChannel.WHATSAPP: patient.notify_whatsapp if patient else False,
    }
    addresses = {
        NotificationChannel.EMAIL: email,
        NotificationChannel.SMS: phone,
        NotificationChannel.WHATSAPP: phone,
    }
    return {channel: addresses[channel] for channel, wanted in wants.items() if wanted}


async def enqueue(
    db: AsyncSession,
    *,
    template: str,
    context: dict,
    language: Language,
    recipients: dict[NotificationChannel, str | None],
    dedupe_key: str,
    scheduled_for: datetime | None = None,
    user_id: UUID | None = None,
    patient_id: UUID | None = None,
    appointment_id: UUID | None = None,
) -> list[Notification]:
    """
    Writes one row per wanted channel. Does **not** commit: the caller
    commits with whatever it was already doing, so a booking and its
    messages are one transaction.
    """
    created: list[Notification] = []
    for channel, address in recipients.items():
        key = f"{dedupe_key}:{channel.value}"
        if await db.scalar(select(Notification.id).where(Notification.dedupe_key == key)):
            continue  # already written by an earlier run of this same action
        rendered = render(template, language, channel, context)
        created.append(
            Notification(
                user_id=user_id,
                patient_id=patient_id,
                appointment_id=appointment_id,
                channel=channel,
                status=NotificationStatus.PENDING if address else NotificationStatus.SKIPPED,
                template=template,
                language=language,
                recipient=address or "",
                subject=rendered.subject,
                body=rendered.body,
                dedupe_key=key,
                scheduled_for=scheduled_for or _now(),
                error=None if address else "No address for this channel",
            )
        )
    db.add_all(created)
    return created


async def cancel_pending(db: AsyncSession, *, appointment_id: UUID, templates_to_cancel: tuple[str, ...]) -> int:
    """Stops messages whose reason has gone (the appointment was cancelled)."""
    result = await db.execute(
        update(Notification)
        .where(
            Notification.appointment_id == appointment_id,
            Notification.template.in_(templates_to_cancel),
            Notification.status == NotificationStatus.PENDING,
        )
        .values(status=NotificationStatus.CANCELLED)
    )
    return result.rowcount or 0


# --- What each event sends ------------------------------------------------------------------


async def _appointment_context(db: AsyncSession, appointment: Appointment, language: Language) -> dict:
    patient = await db.get(Patient, appointment.patient_id)
    doctor = await db.get(Doctor, appointment.doctor_id)
    clinic = await db.get(Clinic, appointment.clinic_id)
    settings = get_settings()
    return {
        "patient_name": patient.full_name if patient else "",
        "doctor_name": doctor.full_name if doctor else "",
        "clinic_name": clinic.name if clinic else "",
        "clinic_phone": (clinic.phone if clinic else None) or "—",
        "address_line": (clinic.address if clinic and clinic.address else ""),
        "when": _local(appointment.scheduled_start, language),
        "appointments_url": f"{settings.frontend_url}/appointments",
        "booking_url": f"{settings.frontend_url}/booking",
        "consultation_url": f"{settings.frontend_url}/consultation",
    }


async def on_appointment_booked(db: AsyncSession, appointment: Appointment, *, paid: bool = False) -> None:
    """Confirmation now, a reminder the day before, aftercare the day after."""
    patient = await db.get(Patient, appointment.patient_id)
    if patient is None:
        return
    settings = get_settings()
    language = patient.preferred_language
    context = await _appointment_context(db, appointment, language)
    recipients = channels_for(patient, email=patient.email, phone=patient.phone)
    common = {
        "language": language,
        "recipients": recipients,
        "user_id": patient.user_id,
        "patient_id": patient.id,
        "appointment_id": appointment.id,
    }

    await enqueue(
        db,
        template=templates.APPOINTMENT_CONFIRMED,
        context={
            **context,
            "payment_line": (
                "" if not paid else ("تم استلام الدفع." if language == Language.AR else "Payment received.")
            ),
        },
        dedupe_key=f"confirmed:{appointment.id}",
        **common,
    )

    reminder_at = appointment.scheduled_start - timedelta(hours=settings.reminder_hours_before)
    if reminder_at > _now():  # a booking for tonight gets no "tomorrow" reminder
        await enqueue(
            db,
            template=templates.APPOINTMENT_REMINDER,
            context=context,
            dedupe_key=f"reminder:{appointment.id}",
            scheduled_for=reminder_at,
            **common,
        )

    await enqueue(
        db,
        template=templates.AFTERCARE_FOLLOWUP,
        context=context,
        dedupe_key=f"aftercare:{appointment.id}",
        scheduled_for=appointment.scheduled_end + timedelta(hours=settings.aftercare_hours_after),
        **common,
    )


async def on_appointment_cancelled(db: AsyncSession, appointment: Appointment, *, refunded: bool = False) -> None:
    """Tells the patient, and stops the reminder and follow-up."""
    patient = await db.get(Patient, appointment.patient_id)
    if patient is None:
        return
    language = patient.preferred_language
    context = await _appointment_context(db, appointment, language)
    refund_line = ""
    if refunded:
        refund_line = (
            "سيتم استرداد المبلغ المدفوع بالكامل." if language == Language.AR else "Your payment is being refunded in full."
        )

    await enqueue(
        db,
        template=templates.APPOINTMENT_CANCELLED,
        context={**context, "refund_line": refund_line},
        language=language,
        recipients=channels_for(patient, email=patient.email, phone=patient.phone),
        dedupe_key=f"cancelled:{appointment.id}",
        user_id=patient.user_id,
        patient_id=patient.id,
        appointment_id=appointment.id,
    )
    await cancel_pending(
        db,
        appointment_id=appointment.id,
        templates_to_cancel=(templates.APPOINTMENT_REMINDER, templates.AFTERCARE_FOLLOWUP),
    )


async def on_payment_paid(db: AsyncSession, payment: Payment) -> None:
    """A receipt for money actually taken."""
    patient = await db.get(Patient, payment.patient_id)
    appointment = await db.get(Appointment, payment.appointment_id) if payment.appointment_id else None
    if patient is None or appointment is None:
        return
    language = patient.preferred_language
    context = await _appointment_context(db, appointment, language)
    amount = f"{Decimal(payment.amount or 0):.2f} {payment.currency}"

    await enqueue(
        db,
        template=templates.PAYMENT_RECEIPT,
        context={**context, "amount": amount, "reference": str(payment.id)[:8].upper()},
        language=language,
        recipients=channels_for(patient, email=patient.email, phone=patient.phone),
        dedupe_key=f"receipt:{payment.id}",
        user_id=patient.user_id,
        patient_id=patient.id,
        appointment_id=appointment.id,
    )


async def on_doctor_decision(db: AsyncSession, doctor: Doctor, *, verified: bool) -> None:
    """The verification decision, with the reason when it's a rejection."""
    user = await db.get(User, doctor.user_id) if doctor.user_id else None
    settings = get_settings()
    # Doctors have no channel preferences of their own yet: email, plus SMS
    # if we have a number, because this decision gates their whole account.
    recipients = {
        NotificationChannel.EMAIL: doctor.email or (user.email if user else None),
        NotificationChannel.SMS: doctor.phone or (user.phone if user else None),
    }
    await enqueue(
        db,
        template=templates.DOCTOR_VERIFIED if verified else templates.DOCTOR_REJECTED,
        context={
            "doctor_name": doctor.full_name,
            "doctor_url": f"{settings.frontend_url}/doctor",
            "reason": doctor.verification_notes or "",
        },
        language=Language.EN,
        recipients=recipients,
        # A doctor can be rejected, resubmit and be approved minutes (or
        # seconds) later, so the key is the decision itself: which way it
        # went, and exactly when it was taken.
        dedupe_key=(
            f"doctor-decision:{doctor.id}:{'verified' if verified else 'rejected'}"
            f":{(doctor.reviewed_at or _now()).isoformat()}"
        ),
        user_id=doctor.user_id,
    )


# --- Sending ------------------------------------------------------------------------------


async def due(db: AsyncSession, *, limit: int = 100, now: datetime | None = None) -> list[Notification]:
    rows = await db.scalars(
        select(Notification)
        .where(
            Notification.status.in_(UNSENT),
            Notification.scheduled_for <= (now or _now()),
            Notification.attempts < MAX_ATTEMPTS,
        )
        .order_by(Notification.scheduled_for)
        .limit(limit)
    )
    return list(rows.all())


async def dispatch_due(db: AsyncSession, notifier: Notifier, *, limit: int = 100, now: datetime | None = None) -> dict:
    """
    Sends everything due. Each message is committed on its own, so one
    bad address can't roll back the others, and a crash mid-run doesn't
    resend what already went out.
    """
    sent = failed = 0
    for notification in await due(db, limit=limit, now=now):
        notification.attempts += 1
        try:
            result = await notifier.send(
                Message(
                    channel=notification.channel,
                    recipient=notification.recipient,
                    subject=notification.subject,
                    body=notification.body,
                )
            )
        except NotificationError as exc:
            notification.error = str(exc)
            # Out of attempts: stop trying and leave it visible as failed.
            if notification.attempts >= MAX_ATTEMPTS:
                notification.status = NotificationStatus.FAILED
            failed += 1
            logger.warning(
                "notification.failed", notification_id=str(notification.id), attempts=notification.attempts, error=str(exc)
            )
        else:
            notification.status = NotificationStatus.SENT
            notification.sent_at = _now()
            notification.provider = result.provider
            notification.provider_message_id = result.message_id
            notification.error = None
            sent += 1
        try:
            await db.commit()
        except IntegrityError:  # pragma: no cover - defensive
            await db.rollback()
    if sent or failed:
        logger.info("notification.dispatch", sent=sent, failed=failed)
    return {"sent": sent, "failed": failed}


async def list_notifications(
    db: AsyncSession,
    page: int,
    page_size: int,
    *,
    status: NotificationStatus | None = None,
    channel: NotificationChannel | None = None,
    patient_id: UUID | None = None,
) -> tuple[list[Notification], int]:
    query = select(Notification)
    if status is not None:
        query = query.where(Notification.status == status)
    if channel is not None:
        query = query.where(Notification.channel == channel)
    if patient_id is not None:
        query = query.where(Notification.patient_id == patient_id)
    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = await db.scalars(
        query.order_by(Notification.scheduled_for.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return list(rows.all()), total
