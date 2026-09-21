from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentPrincipal, OptionalPrincipal, Principal, require_roles
from app.api.permissions import can_manage_schedule
from app.core.exceptions import ForbiddenError
from app.db.session import get_db
from app.models.enums import UserRole
from app.schemas.availability import AvailabilityCreate, AvailabilityRead, AvailabilityUpdate, HoldRead
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
    available: bool | None = Query(
        None, description="Only slots that can be booked now: in the future, not booked, not held by someone else"
    ),
    principal: OptionalPrincipal = None,
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[AvailabilityRead]:
    items, total = await availability_service.list_availability(
        db, page, page_size, doctor_id=doctor_id, clinic_id=clinic_id, is_booked=is_booked,
        start_from=start_from, start_to=start_to, available=available,
        # A patient's own hold doesn't hide the slot from them.
        for_patient_id=principal.patient_id if principal else None,
    )
    return PaginatedResponse.build(items, total, page, page_size)


@router.post("", response_model=AvailabilityRead, status_code=status.HTTP_201_CREATED)
async def create_availability(
    payload: AvailabilityCreate, principal: CurrentPrincipal, db: AsyncSession = Depends(get_db)
) -> AvailabilityRead:
    if not can_manage_schedule(principal, payload.doctor_id, payload.clinic_id):
        raise ForbiddenError("You can only manage your own or your clinic's schedule")
    return await availability_service.create_availability(db, payload)


@router.get("/{availability_id}", response_model=AvailabilityRead)
async def get_availability(availability_id: UUID, db: AsyncSession = Depends(get_db)) -> AvailabilityRead:
    return await availability_service.get_availability(db, availability_id)


@router.patch("/{availability_id}", response_model=AvailabilityRead)
async def update_availability(
    availability_id: UUID, payload: AvailabilityUpdate, principal: CurrentPrincipal, db: AsyncSession = Depends(get_db)
) -> AvailabilityRead:
    slot = await availability_service.get_availability(db, availability_id)
    if not can_manage_schedule(principal, slot.doctor_id, slot.clinic_id):
        raise ForbiddenError("You can only manage your own or your clinic's schedule")
    return await availability_service.update_availability(db, availability_id, payload)


PatientOnly = require_roles(UserRole.PATIENT)


@router.post("/{availability_id}/hold", response_model=HoldRead)
async def hold_slot(
    availability_id: UUID, principal: Principal = Depends(PatientOnly), db: AsyncSession = Depends(get_db)
) -> HoldRead:
    """
    Reserves the slot for the calling patient while they pay (default 10
    minutes; calling again extends it). A patient holds one slot at a time.
    409 `slot_unavailable` if it's booked, in the past, or held by someone else.
    """
    if principal.patient_id is None:
        raise ForbiddenError("Only patients with a profile can hold slots")
    slot = await availability_service.hold_slot(db, availability_id, principal.patient_id)
    return HoldRead(availability_id=slot.id, held_until=slot.held_until)


@router.delete("/{availability_id}/hold", status_code=status.HTTP_204_NO_CONTENT)
async def release_hold(
    availability_id: UUID, principal: Principal = Depends(PatientOnly), db: AsyncSession = Depends(get_db)
) -> None:
    if principal.patient_id is not None:
        await availability_service.release_hold(db, availability_id, principal.patient_id)
