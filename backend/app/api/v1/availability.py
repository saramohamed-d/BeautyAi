from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.availability import AvailabilityCreate, AvailabilityRead, AvailabilityUpdate
from app.schemas.common import PaginatedResponse
from app.services import availability_service

router = APIRouter(prefix="/availability", tags=["availability"])


@router.get("", response_model=PaginatedResponse[AvailabilityRead])
async def list_availability(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    doctor_id: UUID | None = Query(None),
    clinic_id: UUID | None = Query(None),
    is_booked: bool | None = Query(None),
    start_from: datetime | None = Query(None),
    start_to: datetime | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[AvailabilityRead]:
    items, total = await availability_service.list_availability(
        db, page, page_size, doctor_id=doctor_id, clinic_id=clinic_id, is_booked=is_booked,
        start_from=start_from, start_to=start_to,
    )
    return PaginatedResponse.build(items, total, page, page_size)


@router.post("", response_model=AvailabilityRead, status_code=status.HTTP_201_CREATED)
async def create_availability(payload: AvailabilityCreate, db: AsyncSession = Depends(get_db)) -> AvailabilityRead:
    return await availability_service.create_availability(db, payload)


@router.get("/{availability_id}", response_model=AvailabilityRead)
async def get_availability(availability_id: UUID, db: AsyncSession = Depends(get_db)) -> AvailabilityRead:
    return await availability_service.get_availability(db, availability_id)


@router.patch("/{availability_id}", response_model=AvailabilityRead)
async def update_availability(
    availability_id: UUID, payload: AvailabilityUpdate, db: AsyncSession = Depends(get_db)
) -> AvailabilityRead:
    return await availability_service.update_availability(db, availability_id, payload)
