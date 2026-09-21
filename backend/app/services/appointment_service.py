"""
Appointment service: booking, status changes, cancellation, rescheduling.

Booking guarantees (Sprint 6):
1. The slot row is locked (SELECT ... FOR UPDATE) before it's checked,
   so concurrent bookings of one slot run one after the other: the first
   succeeds, the rest get 409 `slot_unavailable`. No 500s.
2. Backstop: the partial unique index "one active appointment per slot"
   (see models/scheduling.py). If anything ever slips past the lock, the
   INSERT fails and is reported as the same 409.
3. `idempotency_key`: retrying a booking with the same key returns the
   original appointment instead of creating a second one or failing.
4. The slot is marked booked (and any hold cleared) in the same
   transaction as the appointment insert.

Cancellation and rescheduling free the old slot in the same transaction,
so it's immediately bookable again.

No ranking or auto-selection of doctors here; that's the doctor search
(doctor_service.search_doctors) and, from Sprint 10, the Booking Agent,
which calls these same functions.
"""

from collections.abc import Collection
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.enums import AppointmentStatus, PaymentStatus
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.procedure import Procedure
from app.models.scheduling import Appointment, Availability
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate
from app.services import doctor_verification_service, notification_service
from app.services.availability_service import SLOT_UNAVAILABLE, ensure_bookable, lock_slot

# Allowed status changes. Cancelled, completed and no-show are final.
TRANSITIONS: dict[AppointmentStatus, set[AppointmentStatus]] = {
    AppointmentStatus.PENDING: {AppointmentStatus.CONFIRMED, AppointmentStatus.CANCELLED},
    AppointmentStatus.CONFIRMED: {
        AppointmentStatus.COMPLETED,
        AppointmentStatus.NO_SHOW,
        AppointmentStatus.CANCELLED,
    },
    AppointmentStatus.CANCELLED: set(),
    AppointmentStatus.COMPLETED: set(),
    AppointmentStatus.NO_SHOW: set(),
}
# Only meaningful once the appointment has started.
AFTER_START_ONLY = {AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW}
ACTIVE = {AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED}

WINDOW_CLOSED = "cancellation_window_closed"
INVALID_TRANSITION = "invalid_status_transition"


async def _get_or_404(db: AsyncSession, model, obj_id: UUID, label: str):
    obj = await db.get(model, obj_id)
    if obj is None:
        raise NotFoundError(f"{label} '{obj_id}' not found")
    return obj


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _deadline(db: AsyncSession, clinic_id: UUID, start: datetime) -> datetime:
    cutoff_hours = await db.scalar(select(Clinic.cancellation_cutoff_hours).where(Clinic.id == clinic_id))
    return start - timedelta(hours=cutoff_hours or 0)


async def _find_by_idempotency_key(db: AsyncSession, key: str) -> Appointment | None:
    return await db.scalar(select(Appointment).where(Appointment.idempotency_key == key))


def _replay(existing: Appointment, data: AppointmentCreate) -> Appointment:
    """A retried request returns the original booking; a key reused for a different patient is a conflict."""
    if existing.patient_id != data.patient_id:
        raise ConflictError("This idempotency_key was already used for a different booking")
    return existing


async def create_appointment(db: AsyncSession, data: AppointmentCreate) -> Appointment:
    if data.idempotency_key:
        existing = await _find_by_idempotency_key(db, data.idempotency_key)
        if existing is not None:
            return _replay(existing, data)

    await _get_or_404(db, Patient, data.patient_id, "Patient")
    doctor = await _get_or_404(db, Doctor, data.doctor_id, "Doctor")
    # Sprint 12: only a verified, active doctor can be booked, whoever books.
    doctor_verification_service.ensure_can_practise(doctor)
    await _get_or_404(db, Clinic, data.clinic_id, "Clinic")
    if data.procedure_id:
        await _get_or_404(db, Procedure, data.procedure_id, "Procedure")

    values = data.model_dump()
    slot: Availability | None = None
    if data.availability_id:
        slot = await lock_slot(db, data.availability_id)
        # Check again under the lock: a concurrent retry of this same request
        # may have booked the slot while we waited for the lock.
        # (The slot lock is released when the request's session closes.)
        if data.idempotency_key and (existing := await _find_by_idempotency_key(db, data.idempotency_key)):
            return _replay(existing, data)
        if slot.doctor_id != data.doctor_id or slot.clinic_id != data.clinic_id:
            raise ValidationAppError("The slot belongs to a different doctor or clinic")
        ensure_bookable(slot, _now(), data.patient_id)
        values["scheduled_start"], values["scheduled_end"] = slot.start_time, slot.end_time

    appointment = Appointment(**values)
    appointment.cancellable_until = await _deadline(db, data.clinic_id, appointment.scheduled_start)
    db.add(appointment)
    if slot is not None:
        slot.is_booked = True
        slot.held_by_patient_id = None
        slot.held_until = None

    # Sprint 15: the confirmation, reminder and follow-up are written in
    # this same transaction — booked and "will be told" are one fact.
    await db.flush()
    await notification_service.on_appointment_booked(db, appointment)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        # Two identical retries raced past the first check: return the winner.
        if data.idempotency_key and (existing := await _find_by_idempotency_key(db, data.idempotency_key)):
            return _replay(existing, data)
        raise ConflictError("This time slot was just taken. Please choose another time.", code=SLOT_UNAVAILABLE) from None

    await db.refresh(appointment)
    return appointment


async def get_appointment(db: AsyncSession, appointment_id: UUID) -> Appointment:
    appointment = await db.get(Appointment, appointment_id)
    if appointment is None:
        raise NotFoundError(f"Appointment '{appointment_id}' not found")
    return appointment


async def _lock_appointment(db: AsyncSession, appointment_id: UUID) -> Appointment:
    """Row-locks the appointment so a cancel and a reschedule of it can't interleave."""
    appointment = await db.scalar(
        select(Appointment)
        .where(Appointment.id == appointment_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if appointment is None:
        raise NotFoundError(f"Appointment '{appointment_id}' not found")
    return appointment


async def list_appointments(
    db: AsyncSession,
    page: int,
    page_size: int,
    patient_id: UUID | None = None,
    doctor_id: UUID | None = None,
    clinic_id: UUID | None = None,
    clinic_ids: Collection[UUID] | None = None,
    status: AppointmentStatus | None = None,
) -> tuple[list[Appointment], int]:
    query = select(Appointment)
    if clinic_ids is not None:
        query = query.where(Appointment.clinic_id.in_(clinic_ids))
    if patient_id:
        query = query.where(Appointment.patient_id == patient_id)
    if doctor_id:
        query = query.where(Appointment.doctor_id == doctor_id)
    if clinic_id:
        query = query.where(Appointment.clinic_id == clinic_id)
    if status is not None:
        query = query.where(Appointment.status == status)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    query = query.order_by(Appointment.scheduled_start.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return list(result.scalars().all()), total or 0


async def _ensure_patient_window_open(db: AsyncSession, appointment: Appointment) -> None:
    # Appointments inserted outside this service (imports, scripts) may lack a
    # stored deadline: fall back to the clinic's current policy, never to "any time".
    deadline = appointment.cancellable_until or await _deadline(db, appointment.clinic_id, appointment.scheduled_start)
    if _now() > deadline:
        raise ConflictError(
            "It's too late to cancel or reschedule online. Please contact the clinic.", code=WINDOW_CLOSED
        )


async def _release_slot(db: AsyncSession, availability_id: UUID | None) -> None:
    if availability_id is not None:
        slot = await lock_slot(db, availability_id)
        slot.is_booked = False


async def update_appointment(
    db: AsyncSession,
    appointment_id: UUID,
    data: AppointmentUpdate,
    *,
    actor_user_id: UUID | None,
    enforce_patient_window: bool,
) -> Appointment:
    """
    Status changes follow TRANSITIONS. Cancelling frees the slot at once.
    `enforce_patient_window` applies the clinic's cancellation cutoff
    (patients); staff may cancel at any time.
    """
    appointment = await _lock_appointment(db, appointment_id)
    new_status = data.status

    if new_status is not None and new_status != appointment.status:
        if new_status not in TRANSITIONS[appointment.status]:
            raise ConflictError(
                f"An appointment can't go from '{appointment.status.value}' to '{new_status.value}'",
                code=INVALID_TRANSITION,
            )
        if new_status in AFTER_START_ONLY and _now() < appointment.scheduled_start:
            raise ConflictError(
                f"An appointment can only be marked '{new_status.value}' after it starts", code=INVALID_TRANSITION
            )
        if new_status == AppointmentStatus.CANCELLED:
            if enforce_patient_window:
                await _ensure_patient_window_open(db, appointment)
            await _release_slot(db, appointment.availability_id)
            appointment.cancelled_at = _now()
            appointment.cancelled_by_user_id = actor_user_id
            appointment.cancellation_reason = data.cancellation_reason
            # Tell the patient, and stop the reminder and follow-up. A
            # payment that has been taken will be refunded (the route does
            # it next), so the message says so.
            paid = await db.scalar(
                select(Payment.id).where(
                    Payment.appointment_id == appointment.id, Payment.status == PaymentStatus.PAID
                )
            )
            await notification_service.on_appointment_cancelled(db, appointment, refunded=bool(paid))
        appointment.status = new_status

    if "notes" in data.model_fields_set:
        appointment.notes = data.notes

    await db.commit()
    await db.refresh(appointment)
    return appointment


async def reschedule_appointment(
    db: AsyncSession,
    appointment_id: UUID,
    new_availability_id: UUID,
    *,
    enforce_patient_window: bool,
) -> Appointment:
    """
    Moves an active appointment to another open slot with the same doctor
    (any of their clinics), atomically: the new slot is booked and the old
    one freed in one transaction. The appointment goes back to `pending`
    because the clinic has to confirm the new time.
    """
    appointment = await _lock_appointment(db, appointment_id)
    if appointment.status not in ACTIVE:
        raise ConflictError(f"A {appointment.status.value} appointment can't be rescheduled", code=INVALID_TRANSITION)
    if enforce_patient_window:
        await _ensure_patient_window_open(db, appointment)
    if new_availability_id == appointment.availability_id:
        return appointment

    # Lock both slots in a fixed (id) order so two opposite reschedules can't deadlock.
    old_id = appointment.availability_id
    locked = {}
    for slot_id in sorted(filter(None, [old_id, new_availability_id]), key=str):
        locked[slot_id] = await lock_slot(db, slot_id)
    new_slot = locked[new_availability_id]

    if new_slot.doctor_id != appointment.doctor_id:
        raise ValidationAppError("You can only reschedule to a time with the same doctor")
    ensure_bookable(new_slot, _now(), appointment.patient_id)

    if old_id is not None:
        locked[old_id].is_booked = False
    new_slot.is_booked = True
    new_slot.held_by_patient_id = None
    new_slot.held_until = None

    appointment.availability_id = new_slot.id
    appointment.clinic_id = new_slot.clinic_id
    appointment.scheduled_start = new_slot.start_time
    appointment.scheduled_end = new_slot.end_time
    appointment.cancellable_until = await _deadline(db, new_slot.clinic_id, new_slot.start_time)
    appointment.status = AppointmentStatus.PENDING

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ConflictError("This time slot was just taken. Please choose another time.", code=SLOT_UNAVAILABLE) from None
    await db.refresh(appointment)
    return appointment
