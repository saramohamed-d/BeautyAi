"""
Availability (bookable slots) and slot holds.

A slot is *bookable* for a patient when it starts in the future, isn't
booked, and isn't held by a different patient. Every write that changes
a slot's booked/held state locks the slot row first (SELECT ... FOR
UPDATE), so two requests for the same slot are processed one after the
other instead of racing.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import ColumnElement, and_, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.services import doctor_verification_service
from app.models.enums import AppointmentStatus
from app.models.scheduling import Appointment, Availability
from app.schemas.availability import AvailabilityCreate, AvailabilityUpdate

SLOT_UNAVAILABLE = "slot_unavailable"


def bookable_conditions(now: datetime, for_patient_id: UUID | None = None) -> list[ColumnElement[bool]]:
    """SQL conditions for "this slot can be booked now (by this patient)"."""
    hold_is_free = or_(Availability.held_until.is_(None), Availability.held_until <= now)
    if for_patient_id is not None:
        hold_is_free = or_(hold_is_free, Availability.held_by_patient_id == for_patient_id)
    return [Availability.is_booked.is_(False), Availability.start_time > now, hold_is_free]


def ensure_bookable(slot: Availability, now: datetime, patient_id: UUID | None) -> None:
    """Python twin of bookable_conditions, for a slot row already locked by the caller."""
    held_by_other = (
        slot.held_until is not None and slot.held_until > now and slot.held_by_patient_id != patient_id
    )
    if slot.is_booked or held_by_other:
        raise ConflictError("This time slot was just taken. Please choose another time.", code=SLOT_UNAVAILABLE)
    if slot.start_time <= now:
        raise ConflictError("This time slot is in the past.", code=SLOT_UNAVAILABLE)


async def lock_slot(db: AsyncSession, availability_id: UUID) -> Availability:
    """Loads a slot with a row lock held until the transaction ends. 404 if it doesn't exist."""
    slot = await db.scalar(
        select(Availability).where(Availability.id == availability_id).with_for_update().execution_options(populate_existing=True)
    )
    if slot is None:
        raise NotFoundError(f"Availability slot '{availability_id}' not found")
    return slot


async def _ensure_doctor_and_clinic_exist(db: AsyncSession, doctor_id: UUID, clinic_id: UUID) -> None:
    doctor = await db.get(Doctor, doctor_id)
    if doctor is None:
        raise NotFoundError(f"Doctor '{doctor_id}' not found")
    # Sprint 12: an unverified doctor has no public presence, so no slots.
    doctor_verification_service.ensure_can_practise(doctor)
    clinic = await db.get(Clinic, clinic_id)
    if clinic is None:
        raise NotFoundError(f"Clinic '{clinic_id}' not found")


async def create_availability(db: AsyncSession, data: AvailabilityCreate) -> Availability:
    await _ensure_doctor_and_clinic_exist(db, data.doctor_id, data.clinic_id)

    slot = Availability(**data.model_dump())
    db.add(slot)
    await db.commit()
    await db.refresh(slot)
    return slot


async def get_availability(db: AsyncSession, availability_id: UUID) -> Availability:
    slot = await db.get(Availability, availability_id)
    if slot is None:
        raise NotFoundError(f"Availability slot '{availability_id}' not found")
    return slot


async def list_availability(
    db: AsyncSession,
    page: int,
    page_size: int,
    doctor_id: UUID | None = None,
    clinic_id: UUID | None = None,
    is_booked: bool | None = None,
    start_from=None,
    start_to=None,
    available: bool | None = None,
    for_patient_id: UUID | None = None,
) -> tuple[list[Availability], int]:
    query = select(Availability)
    if doctor_id:
        query = query.where(Availability.doctor_id == doctor_id)
    if clinic_id:
        query = query.where(Availability.clinic_id == clinic_id)
    if is_booked is not None:
        query = query.where(Availability.is_booked == is_booked)
    if start_from:
        query = query.where(Availability.start_time >= start_from)
    if start_to:
        query = query.where(Availability.start_time <= start_to)
    if available:
        query = query.where(*bookable_conditions(datetime.now(timezone.utc), for_patient_id))

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    query = query.order_by(Availability.start_time.asc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return list(result.scalars().all()), total or 0


async def _has_active_appointment(db: AsyncSession, availability_id: UUID) -> bool:
    return bool(
        await db.scalar(
            select(
                exists().where(
                    Appointment.availability_id == availability_id,
                    Appointment.status != AppointmentStatus.CANCELLED,
                )
            )
        )
    )


async def update_availability(db: AsyncSession, availability_id: UUID, data: AvailabilityUpdate) -> Availability:
    slot = await lock_slot(db, availability_id)
    updates = data.model_dump(exclude_unset=True)

    new_start = updates.get("start_time", slot.start_time)
    new_end = updates.get("end_time", slot.end_time)
    if new_end <= new_start:
        raise ValidationAppError("end_time must be after start_time")

    # Staff may block a free slot (is_booked=true) or move it, but never
    # detach a slot from a live appointment: that would allow double-booking.
    moving = "start_time" in updates or "end_time" in updates
    freeing = updates.get("is_booked") is False
    if (moving or freeing) and await _has_active_appointment(db, availability_id):
        raise ConflictError("This slot has an active appointment. Reschedule or cancel the appointment instead.")

    for field, value in updates.items():
        setattr(slot, field, value)

    await db.commit()
    await db.refresh(slot)
    return slot


async def hold_slot(db: AsyncSession, availability_id: UUID, patient_id: UUID) -> Availability:
    """
    Reserves a slot for a patient on the payment step for `slot_hold_minutes`.

    Holding again extends the hold. A patient holds at most one slot at a
    time: taking a new hold releases their previous one, so going back
    and picking another time doesn't leave the first time blocked.
    """
    now = datetime.now(timezone.utc)
    slot = await lock_slot(db, availability_id)
    ensure_bookable(slot, now, patient_id)

    await db.execute(
        update(Availability)
        .where(and_(Availability.held_by_patient_id == patient_id, Availability.id != availability_id))
        .values(held_by_patient_id=None, held_until=None)
    )
    slot.held_by_patient_id = patient_id
    slot.held_until = now + timedelta(minutes=get_settings().slot_hold_minutes)
    await db.commit()
    await db.refresh(slot)
    return slot


async def release_hold(db: AsyncSession, availability_id: UUID, patient_id: UUID) -> None:
    """Releases the patient's own hold. Releasing a hold you don't have is a no-op."""
    slot = await lock_slot(db, availability_id)
    if slot.held_by_patient_id == patient_id:
        slot.held_by_patient_id = None
        slot.held_until = None
    await db.commit()
