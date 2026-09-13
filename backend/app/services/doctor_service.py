from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.doctor import Doctor
from app.models.enums import VerificationStatus
from app.schemas.doctor import DoctorCreate, DoctorUpdate


async def create_doctor(db: AsyncSession, data: DoctorCreate) -> Doctor:
    if data.email:
        existing = await db.execute(select(Doctor).where(Doctor.email == data.email))
        if existing.scalar_one_or_none() is not None:
            raise ConflictError(f"A doctor with email '{data.email}' already exists")

    doctor = Doctor(**data.model_dump())
    db.add(doctor)
    await db.commit()
    await db.refresh(doctor)
    return doctor


async def get_doctor(db: AsyncSession, doctor_id: UUID) -> Doctor:
    doctor = await db.get(Doctor, doctor_id)
    if doctor is None:
        raise NotFoundError(f"Doctor '{doctor_id}' not found")
    return doctor


async def list_doctors(
    db: AsyncSession,
    page: int,
    page_size: int,
    specialty: str | None = None,
    is_active: bool | None = None,
    verification_status: VerificationStatus | None = None,
) -> tuple[list[Doctor], int]:
    query = select(Doctor)
    if specialty:
        query = query.where(Doctor.specialty.ilike(f"%{specialty}%"))
    if is_active is not None:
        query = query.where(Doctor.is_active == is_active)
    if verification_status is not None:
        query = query.where(Doctor.verification_status == verification_status)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    query = query.order_by(Doctor.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return list(result.scalars().all()), total or 0


async def update_doctor(db: AsyncSession, doctor_id: UUID, data: DoctorUpdate) -> Doctor:
    doctor = await get_doctor(db, doctor_id)

    updates = data.model_dump(exclude_unset=True)
    if "email" in updates and updates["email"] and updates["email"] != doctor.email:
        existing = await db.execute(
            select(Doctor).where(Doctor.email == updates["email"], Doctor.id != doctor_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError(f"A doctor with email '{updates['email']}' already exists")

    for field, value in updates.items():
        setattr(doctor, field, value)

    await db.commit()
    await db.refresh(doctor)
    return doctor
