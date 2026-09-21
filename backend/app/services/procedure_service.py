from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.procedure import Procedure
from app.schemas.procedure import ProcedureCreate, ProcedureUpdate


async def create_procedure(db: AsyncSession, data: ProcedureCreate) -> Procedure:
    existing = await db.execute(select(Procedure).where(Procedure.slug == data.slug))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError(f"A procedure with slug '{data.slug}' already exists")

    procedure = Procedure(**data.model_dump())
    db.add(procedure)
    await db.commit()
    await db.refresh(procedure)
    return procedure


async def get_procedure(db: AsyncSession, procedure_id: UUID) -> Procedure:
    procedure = await db.get(Procedure, procedure_id)
    if procedure is None:
        raise NotFoundError(f"Procedure '{procedure_id}' not found")
    return procedure


async def list_procedures(
    db: AsyncSession, page: int, page_size: int, category: str | None = None
) -> tuple[list[Procedure], int]:
    query = select(Procedure)
    if category:
        query = query.where(Procedure.category.ilike(f"%{category}%"))

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    query = query.order_by(Procedure.name.asc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return list(result.scalars().all()), total or 0


async def update_procedure(db: AsyncSession, procedure_id: UUID, data: ProcedureUpdate) -> Procedure:
    procedure = await get_procedure(db, procedure_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(procedure, field, value)
    await db.commit()
    await db.refresh(procedure)
    return procedure
