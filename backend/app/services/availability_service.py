from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.scheduling import Availability
from app.schemas.availability import AvailabilityCreate, AvailabilityUpdate


async def _ensure_doctor_and_clinic_exist(db: AsyncSession, doctor_id: UUID, clinic_id: UUID) -> None:
    doctor = await db.get(Doctor, doctor_id)
    if doctor is None:
        raise NotFoundError(f"Doctor '{doctor_id}' not found")
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

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    query = query.order_by(Availability.start_time.asc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return list(result.scalars().all()), total or 0


async def update_availability(db: AsyncSession, availability_id: UUID, data: AvailabilityUpdate) -> Availability:
    slot = await get_availability(db, availability_id)
    updates = data.model_dump(exclude_unset=True)

    new_start = updates.get("start_time", slot.start_time)
    new_end = updates.get("end_time", slot.end_time)
    if new_end <= new_start:
        from app.core.exceptions import ValidationAppError

        raise ValidationAppError("end_time must be after start_time")

    for field, value in updates.items():
        setattr(slot, field, value)

    await db.commit()
    await db.refresh(slot)
    return slot
