from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.enums import VerificationStatus
from app.schemas.common import PaginatedResponse
from app.schemas.doctor import DoctorCreate, DoctorRead, DoctorUpdate
from app.services import doctor_service

router = APIRouter(prefix="/doctors", tags=["doctors"])


@router.get("", response_model=PaginatedResponse[DoctorRead])
async def list_doctors(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    specialty: str | None = Query(None),
    is_active: bool | None = Query(None),
    verification_status: VerificationStatus | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[DoctorRead]:
    items, total = await doctor_service.list_doctors(
        db, page, page_size, specialty=specialty, is_active=is_active, verification_status=verification_status
    )
    return PaginatedResponse.build(items, total, page, page_size)


@router.post("", response_model=DoctorRead, status_code=status.HTTP_201_CREATED)
async def create_doctor(payload: DoctorCreate, db: AsyncSession = Depends(get_db)) -> DoctorRead:
    return await doctor_service.create_doctor(db, payload)


@router.get("/{doctor_id}", response_model=DoctorRead)
async def get_doctor(doctor_id: UUID, db: AsyncSession = Depends(get_db)) -> DoctorRead:
    return await doctor_service.get_doctor(db, doctor_id)


@router.patch("/{doctor_id}", response_model=DoctorRead)
async def update_doctor(doctor_id: UUID, payload: DoctorUpdate, db: AsyncSession = Depends(get_db)) -> DoctorRead:
    return await doctor_service.update_doctor(db, doctor_id, payload)
