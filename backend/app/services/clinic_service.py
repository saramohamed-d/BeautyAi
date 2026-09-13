from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.clinic import Clinic
from app.schemas.clinic import ClinicCreate, ClinicUpdate


async def create_clinic(db: AsyncSession, data: ClinicCreate) -> Clinic:
    clinic = Clinic(**data.model_dump())
    db.add(clinic)
    await db.commit()
    await db.refresh(clinic)
    return clinic


async def get_clinic(db: AsyncSession, clinic_id: UUID) -> Clinic:
    clinic = await db.get(Clinic, clinic_id)
    if clinic is None:
        raise NotFoundError(f"Clinic '{clinic_id}' not found")
    return clinic


async def list_clinics(
    db: AsyncSession, page: int, page_size: int, city: str | None = None, is_active: bool | None = None
) -> tuple[list[Clinic], int]:
    query = select(Clinic)
    if city:
        query = query.where(Clinic.city.ilike(f"%{city}%"))
    if is_active is not None:
        query = query.where(Clinic.is_active == is_active)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    query = query.order_by(Clinic.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return list(result.scalars().all()), total or 0


async def update_clinic(db: AsyncSession, clinic_id: UUID, data: ClinicUpdate) -> Clinic:
    clinic = await get_clinic(db, clinic_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(clinic, field, value)
    await db.commit()
    await db.refresh(clinic)
    return clinic
