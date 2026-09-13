"""
Patient service layer.

Design decision: every service function takes an AsyncSession as its
first argument (dependency-injected by the route via Depends(get_db))
rather than opening its own session. This lets a route compose several
service calls in one transaction when needed (not used yet in Sprint 2,
but Sprint 14's booking flow will need exactly this: check availability
+ create appointment + mark slot booked, atomically).
"""

from uuid import UUID

from sqlalchemy import func, or_, select

from app.core.exceptions import ConflictError, NotFoundError
from app.models.patient import Patient
from app.schemas.patient import PatientCreate, PatientUpdate
from sqlalchemy.ext.asyncio import AsyncSession


async def create_patient(db: AsyncSession, data: PatientCreate) -> Patient:
    existing = await db.execute(select(Patient).where(Patient.phone == data.phone))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError(f"A patient with phone '{data.phone}' already exists")

    if data.email:
        existing_email = await db.execute(select(Patient).where(Patient.email == data.email))
        if existing_email.scalar_one_or_none() is not None:
            raise ConflictError(f"A patient with email '{data.email}' already exists")

    patient = Patient(**data.model_dump())
    db.add(patient)
    await db.commit()
    await db.refresh(patient)
    return patient


async def get_patient(db: AsyncSession, patient_id: UUID) -> Patient:
    patient = await db.get(Patient, patient_id)
    if patient is None:
        raise NotFoundError(f"Patient '{patient_id}' not found")
    return patient


async def list_patients(
    db: AsyncSession, page: int, page_size: int, search: str | None = None
) -> tuple[list[Patient], int]:
    query = select(Patient)
    if search:
        pattern = f"%{search}%"
        query = query.where(or_(Patient.full_name.ilike(pattern), Patient.phone.ilike(pattern)))

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    query = query.order_by(Patient.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return list(result.scalars().all()), total or 0


async def update_patient(db: AsyncSession, patient_id: UUID, data: PatientUpdate) -> Patient:
    patient = await get_patient(db, patient_id)

    updates = data.model_dump(exclude_unset=True)
    if "email" in updates and updates["email"] and updates["email"] != patient.email:
        existing_email = await db.execute(
            select(Patient).where(Patient.email == updates["email"], Patient.id != patient_id)
        )
        if existing_email.scalar_one_or_none() is not None:
            raise ConflictError(f"A patient with email '{updates['email']}' already exists")

    for field, value in updates.items():
        setattr(patient, field, value)

    await db.commit()
    await db.refresh(patient)
    return patient
