from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.conversation import Conversation, Intake
from app.models.enums import IntakeStatus
from app.models.patient import Patient
from app.schemas.intake import IntakeCreate, IntakeUpdate


async def create_intake(db: AsyncSession, data: IntakeCreate) -> Intake:
    conversation = await db.get(Conversation, data.conversation_id)
    if conversation is None:
        raise NotFoundError(f"Conversation '{data.conversation_id}' not found")

    if data.patient_id:
        patient = await db.get(Patient, data.patient_id)
        if patient is None:
            raise NotFoundError(f"Patient '{data.patient_id}' not found")

    existing = await db.execute(select(Intake).where(Intake.conversation_id == data.conversation_id))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError(f"Conversation '{data.conversation_id}' already has an intake")

    intake = Intake(**data.model_dump())
    db.add(intake)
    await db.commit()
    await db.refresh(intake)
    return intake


async def get_intake(db: AsyncSession, intake_id: UUID) -> Intake:
    intake = await db.get(Intake, intake_id)
    if intake is None:
        raise NotFoundError(f"Intake '{intake_id}' not found")
    return intake


async def list_intakes(
    db: AsyncSession,
    page: int,
    page_size: int,
    conversation_id: UUID | None = None,
    patient_id: UUID | None = None,
    status: IntakeStatus | None = None,
) -> tuple[list[Intake], int]:
    query = select(Intake)
    if conversation_id:
        query = query.where(Intake.conversation_id == conversation_id)
    if patient_id:
        query = query.where(Intake.patient_id == patient_id)
    if status is not None:
        query = query.where(Intake.status == status)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    query = query.order_by(Intake.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return list(result.scalars().all()), total or 0


async def update_intake(db: AsyncSession, intake_id: UUID, data: IntakeUpdate) -> Intake:
    intake = await get_intake(db, intake_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(intake, field, value)
    await db.commit()
    await db.refresh(intake)
    return intake
