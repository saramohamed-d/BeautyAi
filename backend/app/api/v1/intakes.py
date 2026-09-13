from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.enums import IntakeStatus
from app.schemas.common import PaginatedResponse
from app.schemas.intake import IntakeCreate, IntakeRead, IntakeUpdate
from app.services import intake_service

router = APIRouter(prefix="/intakes", tags=["intakes"])


@router.get("", response_model=PaginatedResponse[IntakeRead])
async def list_intakes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    conversation_id: UUID | None = Query(None),
    patient_id: UUID | None = Query(None),
    status_filter: IntakeStatus | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[IntakeRead]:
    items, total = await intake_service.list_intakes(
        db, page, page_size, conversation_id=conversation_id, patient_id=patient_id, status=status_filter
    )
    return PaginatedResponse.build(items, total, page, page_size)


@router.post("", response_model=IntakeRead, status_code=status.HTTP_201_CREATED)
async def create_intake(payload: IntakeCreate, db: AsyncSession = Depends(get_db)) -> IntakeRead:
    return await intake_service.create_intake(db, payload)


@router.get("/{intake_id}", response_model=IntakeRead)
async def get_intake(intake_id: UUID, db: AsyncSession = Depends(get_db)) -> IntakeRead:
    return await intake_service.get_intake(db, intake_id)


@router.patch("/{intake_id}", response_model=IntakeRead)
async def update_intake(intake_id: UUID, payload: IntakeUpdate, db: AsyncSession = Depends(get_db)) -> IntakeRead:
    return await intake_service.update_intake(db, intake_id, payload)
