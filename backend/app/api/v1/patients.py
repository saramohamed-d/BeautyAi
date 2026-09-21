from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminPrincipal, CurrentPrincipal
from app.api.permissions import can_view_patient
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.schemas.common import PaginatedResponse
from app.schemas.patient import PatientCreate, PatientRead, PatientUpdate
from app.services import patient_service

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("", response_model=PaginatedResponse[PatientRead])
async def list_patients(
    _: AdminPrincipal,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, description="Search by name or phone"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[PatientRead]:
    """Platform admins only: the full patient directory is personal health-adjacent data."""
    items, total = await patient_service.list_patients(db, page, page_size, search)
    return PaginatedResponse.build(items, total, page, page_size)


@router.post("", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
async def create_patient(payload: PatientCreate, _: AdminPrincipal, db: AsyncSession = Depends(get_db)) -> PatientRead:
    """Creates a profile without a login (patients sign themselves up via POST /auth/register)."""
    return await patient_service.create_patient(db, payload)


@router.get("/{patient_id}", response_model=PatientRead)
async def get_patient(patient_id: UUID, principal: CurrentPrincipal, db: AsyncSession = Depends(get_db)) -> PatientRead:
    """The patient, admins, and doctors / clinic admins who have an appointment with them."""
    if not await can_view_patient(db, principal, patient_id):
        raise NotFoundError(f"Patient '{patient_id}' not found")
    return await patient_service.get_patient(db, patient_id)


@router.patch("/{patient_id}", response_model=PatientRead)
async def update_patient(
    patient_id: UUID, payload: PatientUpdate, principal: CurrentPrincipal, db: AsyncSession = Depends(get_db)
) -> PatientRead:
    """The patient themself or a platform admin."""
    if not (principal.is_admin or principal.patient_id == patient_id):
        raise NotFoundError(f"Patient '{patient_id}' not found")
    return await patient_service.update_patient(db, patient_id, payload)
