"""
Appointment service.

Design decision: creation here does only DETERMINISTIC, schema-backed
validation — not booking intelligence:
  1. patient/doctor/clinic/procedure referenced by ID actually exist (404)
  2. if an availability_id is given, that slot exists and isn't already
     booked (409) — mirrors the DB's own UNIQUE(availability_id) guard,
     but returns a clean 409 instead of surfacing a raw IntegrityError
  3. idempotency_key reuse is rejected (409) — the actual duplicate-retry
     guard is the DB's UNIQUE constraint; this is a friendlier pre-check
  4. on success, if an availability_id was given, the slot is marked
     is_booked=True in the SAME transaction as the appointment insert,
     so the two can never disagree.

No scoring, no candidate ranking, no auto-selection of doctor/slot — that
is Sprint 11 (matching) and Sprint 14 (real booking flow) territory.
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.procedure import Procedure
from app.models.scheduling import Appointment, Availability
from app.models.enums import AppointmentStatus
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate


async def _get_or_404(db: AsyncSession, model, obj_id: UUID, label: str):
    obj = await db.get(model, obj_id)
    if obj is None:
        raise NotFoundError(f"{label} '{obj_id}' not found")
    return obj


async def create_appointment(db: AsyncSession, data: AppointmentCreate) -> Appointment:
    await _get_or_404(db, Patient, data.patient_id, "Patient")
    await _get_or_404(db, Doctor, data.doctor_id, "Doctor")
    await _get_or_404(db, Clinic, data.clinic_id, "Clinic")
    if data.procedure_id:
        await _get_or_404(db, Procedure, data.procedure_id, "Procedure")

    slot: Availability | None = None
    if data.availability_id:
        slot = await _get_or_404(db, Availability, data.availability_id, "Availability slot")
        if slot.is_booked:
            raise ConflictError(f"Availability slot '{data.availability_id}' is already booked")

    if data.idempotency_key:
        existing = await db.execute(
            select(Appointment).where(Appointment.idempotency_key == data.idempotency_key)
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError(f"An appointment with idempotency_key '{data.idempotency_key}' already exists")

    appointment = Appointment(**data.model_dump())
    db.add(appointment)

    if slot is not None:
        slot.is_booked = True

    await db.commit()
    await db.refresh(appointment)
    return appointment


async def get_appointment(db: AsyncSession, appointment_id: UUID) -> Appointment:
    appointment = await db.get(Appointment, appointment_id)
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
    status: AppointmentStatus | None = None,
) -> tuple[list[Appointment], int]:
    query = select(Appointment)
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


async def update_appointment(db: AsyncSession, appointment_id: UUID, data: AppointmentUpdate) -> Appointment:
    appointment = await get_appointment(db, appointment_id)

    # Freeing a slot back up: if an appointment tied to a booked slot is
    # cancelled, release the slot so it becomes bookable again. This is a
    # basic data-consistency rule, not scheduling intelligence.
    updates = data.model_dump(exclude_unset=True)
    if updates.get("status") == AppointmentStatus.CANCELLED and appointment.availability_id:
        slot = await db.get(Availability, appointment.availability_id)
        if slot is not None:
            slot.is_booked = False

    for field, value in updates.items():
        setattr(appointment, field, value)

    await db.commit()
    await db.refresh(appointment)
    return appointment
