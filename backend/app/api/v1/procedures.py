from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.common import PaginatedResponse
from app.schemas.procedure import ProcedureCreate, ProcedureRead, ProcedureUpdate
from app.services import procedure_service

router = APIRouter(prefix="/procedures", tags=["procedures"])


@router.get("", response_model=PaginatedResponse[ProcedureRead])
async def list_procedures(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ProcedureRead]:
    items, total = await procedure_service.list_procedures(db, page, page_size, category=category)
    return PaginatedResponse.build(items, total, page, page_size)


@router.post("", response_model=ProcedureRead, status_code=status.HTTP_201_CREATED)
async def create_procedure(payload: ProcedureCreate, db: AsyncSession = Depends(get_db)) -> ProcedureRead:
    return await procedure_service.create_procedure(db, payload)


@router.get("/{procedure_id}", response_model=ProcedureRead)
async def get_procedure(procedure_id: UUID, db: AsyncSession = Depends(get_db)) -> ProcedureRead:
    return await procedure_service.get_procedure(db, procedure_id)


@router.patch("/{procedure_id}", response_model=ProcedureRead)
async def update_procedure(
    procedure_id: UUID, payload: ProcedureUpdate, db: AsyncSession = Depends(get_db)
) -> ProcedureRead:
    return await procedure_service.update_procedure(db, procedure_id, payload)
