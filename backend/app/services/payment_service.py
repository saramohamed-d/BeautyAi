"""
Payments: checkout, gateway events, refunds (Sprint 11; docs/payments.md).

Online payment comes BEFORE the appointment:
1. start_checkout holds the slot for the patient for PAYMENT_WINDOW_MINUTES,
   records a PENDING payment and asks the gateway for a checkout URL.
2. The patient pays on the gateway's page.
3. The gateway's signed webhook reaches handle_event. On success the
   appointment is created with the Sprint 6 booking code (row lock, "one
   active appointment per slot", idempotency key per payment), so a paid
   slot can't be double-booked.
4. If the money arrives but the slot is gone (the hold expired and someone
   else booked it) or the amount doesn't match, the payment is refunded
   automatically; if the refund call fails it's marked NEEDS_REFUND for
   an admin. Nobody pays for nothing silently.

Every webhook is stored once (PaymentEvent, unique per provider event),
so duplicates and retries change nothing. The browser returning from
checkout never changes a payment's status.

"Pay at clinic" creates the appointment immediately (payment DUE_AT_CLINIC).
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.models.clinic import ClinicStaff
from app.models.enums import PaymentMethod, PaymentStatus
from app.models.patient import Patient
from app.models.payment import Payment, PaymentEvent
from app.models.scheduling import Appointment
from app.payments.gateways import CheckoutRequest, Customer, GatewayEvent, PaymentGateway, to_cents
from app.schemas.appointment import AppointmentCreate
from app.services import appointment_service, notification_service
from app.services.availability_service import ensure_bookable, lock_slot

logger = get_logger(__name__)

ONLINE_UNAVAILABLE = "online_payment_unavailable"
# A paid event may still arrive for these (e.g. after a declined first try, or late).
_PAYABLE = {PaymentStatus.PENDING, PaymentStatus.FAILED, PaymentStatus.EXPIRED}
# Grace before a still-pending payment is shown as expired (the gateway may be slow).
_EXPIRY_GRACE = timedelta(minutes=2)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def consultation_fee(db: AsyncSession, doctor_id: UUID, clinic_id: UUID) -> Decimal | None:
    fee = await db.scalar(
        select(ClinicStaff.consultation_fee).where(
            ClinicStaff.clinic_id == clinic_id, ClinicStaff.doctor_id == doctor_id, ClinicStaff.is_active.is_(True)
        )
    )
    return Decimal(fee) if fee is not None else None


async def available_methods(db: AsyncSession, doctor_id: UUID, clinic_id: UUID, gateway: PaymentGateway):
    fee = await consultation_fee(db, doctor_id, clinic_id)
    online = gateway.online_methods() if fee is not None else []
    return fee, [*online, PaymentMethod.PAY_AT_CLINIC]


def _customer(patient: Patient) -> Customer:
    first, _, last = patient.full_name.strip().partition(" ")
    return Customer(first_name=first, last_name=last or first, email=patient.email or "", phone=patient.phone)


async def start_checkout(
    db: AsyncSession,
    *,
    patient: Patient,
    availability_id: UUID,
    method: PaymentMethod,
    idempotency_key: str,
    gateway: PaymentGateway,
) -> tuple[Payment, Appointment | None]:
    existing = await db.scalar(select(Payment).where(Payment.idempotency_key == idempotency_key))
    if existing is not None:
        if existing.patient_id != patient.id:
            raise ConflictError("This idempotency_key was already used")
        appointment = await db.get(Appointment, existing.appointment_id) if existing.appointment_id else None
        return existing, appointment

    now = _now()
    slot = await lock_slot(db, availability_id)
    ensure_bookable(slot, now, patient.id)
    fee, methods = await available_methods(db, slot.doctor_id, slot.clinic_id, gateway)
    if method not in methods:
        raise ConflictError(
            "Online payment isn't available for this appointment. You can pay at the clinic.", code=ONLINE_UNAVAILABLE
        )

    if method == PaymentMethod.PAY_AT_CLINIC:
        appointment = await appointment_service.create_appointment(
            db,
            AppointmentCreate(
                patient_id=patient.id, doctor_id=slot.doctor_id, clinic_id=slot.clinic_id, availability_id=slot.id,
                scheduled_start=slot.start_time, scheduled_end=slot.end_time, idempotency_key=f"pay:{idempotency_key}",
            ),
        )
        payment = Payment(
            patient_id=patient.id, availability_id=slot.id, appointment_id=appointment.id,
            doctor_id=appointment.doctor_id, clinic_id=appointment.clinic_id, amount=fee, method=method,
            status=PaymentStatus.DUE_AT_CLINIC, provider="clinic", idempotency_key=idempotency_key,
        )
        db.add(payment)
        await db.commit()
        await db.refresh(payment)
        return payment, appointment

    # Online: keep the slot for this patient while they're on the gateway's page.
    window = timedelta(minutes=get_settings().payment_window_minutes)
    slot.held_by_patient_id, slot.held_until = patient.id, now + window
    payment = Payment(
        patient_id=patient.id, availability_id=slot.id, doctor_id=slot.doctor_id, clinic_id=slot.clinic_id,
        amount=fee, method=method, status=PaymentStatus.PENDING, provider=gateway.name,
        idempotency_key=idempotency_key, expires_at=slot.held_until,
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    settings = get_settings()
    try:
        session = await gateway.create_checkout(
            CheckoutRequest(
                payment_id=str(payment.id), amount=Decimal(payment.amount), currency=payment.currency, method=method,
                description="Beauty AI consultation", customer=_customer(patient),
                return_url=f"{settings.frontend_url}/payment/return?payment_id={payment.id}",
                notification_url=f"{settings.public_api_url}/api/v1/payments/webhooks/{gateway.name}",
                expires_in_seconds=int(window.total_seconds()),
            )
        )
    except Exception as exc:
        payment.status, payment.failure_reason = PaymentStatus.FAILED, "Could not start checkout"
        await db.commit()
        raise exc
    payment.provider_order_id, payment.checkout_url = session.provider_order_id, session.checkout_url
    await db.commit()
    await db.refresh(payment)
    logger.info("payment.checkout_started", payment_id=str(payment.id), provider=gateway.name, method=method.value)
    return payment, None


async def refund(db: AsyncSession, payment: Payment, gateway: PaymentGateway, reason: str) -> None:
    """
    Refunds a payment and records the outcome: REFUNDED, or NEEDS_REFUND
    when the gateway refuses, which is the pile an admin works through
    (Sprint 14). Used automatically (slot lost, amount mismatch,
    cancellation) and by hand from the admin dashboard.
    """
    payment.status, payment.failure_reason = PaymentStatus.REFUND_PENDING, reason
    await db.commit()
    ok = bool(payment.provider_transaction_id) and await gateway.refund(
        payment.provider_transaction_id, Decimal(payment.amount or 0)
    )
    if ok:
        payment.status, payment.refunded_at = PaymentStatus.REFUNDED, _now()
    else:
        payment.status = PaymentStatus.NEEDS_REFUND
        logger.error("payment.refund_failed", payment_id=str(payment.id), reason=reason)
    await db.commit()


async def handle_event(db: AsyncSession, event: GatewayEvent, gateway: PaymentGateway) -> Payment | None:
    """Applies one verified gateway event. Safe to call repeatedly with the same event."""
    record = PaymentEvent(
        provider=gateway.name, event_key=f"{event.transaction_id}:{event.outcome}", outcome=event.outcome,
        payload=event.payload,
    )
    db.add(record)
    try:
        # Stored in its own transaction first: it's the audit trail and the
        # duplicate guard, and must survive whatever happens next.
        await db.commit()
    except IntegrityError:
        await db.rollback()
        logger.info("payment.duplicate_event", provider=gateway.name, transaction_id=event.transaction_id)
        return None

    payment = await db.scalar(
        select(Payment).where(Payment.provider_order_id == event.provider_order_id).with_for_update()
    )
    if payment is None:
        record.handled = False
        await db.commit()
        logger.warning("payment.unknown_order", provider=gateway.name, order_id=event.provider_order_id)
        return None
    record.payment_id = payment.id

    if event.outcome == "pending":
        await db.commit()
    elif event.outcome == "refunded":
        payment.status, payment.refunded_at = PaymentStatus.REFUNDED, _now()
        await db.commit()
    elif event.outcome == "failed":
        if payment.status == PaymentStatus.PENDING:
            payment.status, payment.failure_reason = PaymentStatus.FAILED, "The payment was declined"
            payment.provider_transaction_id = event.transaction_id
        await db.commit()  # the hold stays until it expires, so the patient can try again
    elif payment.status not in _PAYABLE:
        await db.commit()  # already paid / refunded: nothing to do
    else:
        await _fulfil(db, payment, event, gateway)
    await db.refresh(payment)
    return payment


async def _fulfil(db: AsyncSession, payment: Payment, event: GatewayEvent, gateway: PaymentGateway) -> None:
    payment.provider_transaction_id, payment.paid_at = event.transaction_id, _now()
    if payment.amount is None or event.amount_cents != to_cents(Decimal(payment.amount)):
        logger.error("payment.amount_mismatch", payment_id=str(payment.id), received=event.amount_cents)
        await refund(db, payment, gateway, "The amount received didn't match the fee")
        return
    slot_id, transaction_id, paid_at = payment.availability_id, payment.provider_transaction_id, payment.paid_at
    try:
        if slot_id is None:
            raise NotFoundError("The slot was removed")
        slot = await lock_slot(db, slot_id)
        appointment = await appointment_service.create_appointment(
            db,
            AppointmentCreate(
                patient_id=payment.patient_id, doctor_id=payment.doctor_id, clinic_id=payment.clinic_id,
                availability_id=slot_id, scheduled_start=slot.start_time, scheduled_end=slot.end_time,
                idempotency_key=f"payment:{payment.id}",
            ),
        )
    except (ConflictError, NotFoundError, ForbiddenError):
        # The slot went to someone else or disappeared, or the doctor stopped
        # being bookable (verification withdrawn between checkout and payment).
        # The booking may have rolled back, so keep what we know about the
        # money, then give it back rather than holding it for nothing.
        payment.provider_transaction_id, payment.paid_at = transaction_id, paid_at
        logger.warning("payment.slot_lost", payment_id=str(payment.id))
        await refund(db, payment, gateway, "The time was no longer available")
        return
    payment.status, payment.appointment_id = PaymentStatus.PAID, appointment.id
    # Sprint 15: receipt now, in the same transaction as the payment.
    await notification_service.on_payment_paid(db, payment)
    await db.commit()
    logger.info("payment.paid", payment_id=str(payment.id), appointment_id=str(appointment.id))


async def refund_for_appointment(db: AsyncSession, appointment_id: UUID, gateway: PaymentGateway) -> Payment | None:
    """Refunds a paid appointment's payment after it was cancelled."""
    payment = await db.scalar(
        select(Payment).where(Payment.appointment_id == appointment_id, Payment.status == PaymentStatus.PAID).with_for_update()
    )
    if payment is not None:
        await refund(db, payment, gateway, "Appointment cancelled")
        await db.refresh(payment)
    return payment


def display_status(payment: Payment) -> PaymentStatus:
    """A pending payment past its window (plus grace) is shown as expired; a late webhook can still complete it."""
    if payment.status == PaymentStatus.PENDING and payment.expires_at and _now() > payment.expires_at + _EXPIRY_GRACE:
        return PaymentStatus.EXPIRED
    return payment.status
