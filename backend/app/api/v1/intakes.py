from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminPrincipal, Principal, require_roles
from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.session import get_db
from app.models.enums import IntakeStatus, UserRole
from app.schemas.common import PaginatedResponse
from app.schemas.intake import IntakeCreate, IntakeRead, IntakeUpdate
from app.services import intake_service

# Intakes are structured data extracted from a conversation. They are
# written by the backend (the Intake Agent, Sprint 9) or an admin — never
# directly by patients, who can only read their own.
router = APIRouter(prefix="/intakes", tags=["intakes"])
PatientOrAdmin = require_roles(UserRole.PATIENT, UserRole.PLATFORM_ADMIN)


@router.get("", response_model=PaginatedResponse[IntakeRead])
async def list_intakes(
    principal: Principal = Depends(PatientOrAdmin),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    conversation_id: UUID | None = Query(None),
    patient_id: UUID | None = Query(None),
    status_filter: IntakeStatus | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[IntakeRead]:
    if not principal.is_admin:
        if principal.patient_id is None:
            return PaginatedResponse.build([], 0, page, page_size)
        if patient_id is not None and patient_id != principal.patient_id:
            raise ForbiddenError("You can only list your own intakes")
        patient_id = principal.patient_id
    items, total = await intake_service.list_intakes(
        db, page, page_size, conversation_id=conversation_id, patient_id=patient_id, status=status_filter
    )
    return PaginatedResponse.build(items, total, page, page_size)


@router.post("", response_model=IntakeRead, status_code=status.HTTP_201_CREATED)
async def create_intake(payload: IntakeCreate, _: AdminPrincipal, db: AsyncSession = Depends(get_db)) -> IntakeRead:
    return await intake_service.create_intake(db, payload)


@router.get("/{intake_id}", response_model=IntakeRead)
async def get_intake(
    intake_id: UUID, principal: Principal = Depends(PatientOrAdmin), db: AsyncSession = Depends(get_db)
) -> IntakeRead:
    intake = await intake_service.get_intake(db, intake_id)
    if not principal.is_admin and (principal.patient_id is None or intake.patient_id != principal.patient_id):
        raise NotFoundError(f"Intake '{intake_id}' not found")
    return intake


@router.patch("/{intake_id}", response_model=IntakeRead)
async def update_intake(
    intake_id: UUID, payload: IntakeUpdate, _: AdminPrincipal, db: AsyncSession = Depends(get_db)
) -> IntakeRead:
    return await intake_service.update_intake(db, intake_id, payload)
