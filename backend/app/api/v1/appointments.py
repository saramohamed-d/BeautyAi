from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.enums import AppointmentStatus
from app.schemas.appointment import AppointmentCreate, AppointmentRead, AppointmentUpdate
from app.schemas.common import PaginatedResponse
from app.services import appointment_service

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.get("", response_model=PaginatedResponse[AppointmentRead])
async def list_appointments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    patient_id: UUID | None = Query(None),
    doctor_id: UUID | None = Query(None),
    clinic_id: UUID | None = Query(None),
    status_filter: AppointmentStatus | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[AppointmentRead]:
    items, total = await appointment_service.list_appointments(
        db, page, page_size, patient_id=patient_id, doctor_id=doctor_id, clinic_id=clinic_id, status=status_filter
    )
    return PaginatedResponse.build(items, total, page, page_size)


@router.post("", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED)
async def create_appointment(payload: AppointmentCreate, db: AsyncSession = Depends(get_db)) -> AppointmentRead:
    return await appointment_service.create_appointment(db, payload)


@router.get("/{appointment_id}", response_model=AppointmentRead)
async def get_appointment(appointment_id: UUID, db: AsyncSession = Depends(get_db)) -> AppointmentRead:
    return await appointment_service.get_appointment(db, appointment_id)


@router.patch("/{appointment_id}", response_model=AppointmentRead)
async def update_appointment(
    appointment_id: UUID, payload: AppointmentUpdate, db: AsyncSession = Depends(get_db)
) -> AppointmentRead:
    return await appointment_service.update_appointment(db, appointment_id, payload)
