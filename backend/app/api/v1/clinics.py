from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.clinic import ClinicCreate, ClinicRead, ClinicUpdate
from app.schemas.common import PaginatedResponse
from app.services import clinic_service

router = APIRouter(prefix="/clinics", tags=["clinics"])


@router.get("", response_model=PaginatedResponse[ClinicRead])
async def list_clinics(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    city: str | None = Query(None),
    is_active: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ClinicRead]:
    items, total = await clinic_service.list_clinics(db, page, page_size, city=city, is_active=is_active)
    return PaginatedResponse.build(items, total, page, page_size)


@router.post("", response_model=ClinicRead, status_code=status.HTTP_201_CREATED)
async def create_clinic(payload: ClinicCreate, db: AsyncSession = Depends(get_db)) -> ClinicRead:
    return await clinic_service.create_clinic(db, payload)


@router.get("/{clinic_id}", response_model=ClinicRead)
async def get_clinic(clinic_id: UUID, db: AsyncSession = Depends(get_db)) -> ClinicRead:
    return await clinic_service.get_clinic(db, clinic_id)


@router.patch("/{clinic_id}", response_model=ClinicRead)
async def update_clinic(clinic_id: UUID, payload: ClinicUpdate, db: AsyncSession = Depends(get_db)) -> ClinicRead:
    return await clinic_service.update_clinic(db, clinic_id, payload)
