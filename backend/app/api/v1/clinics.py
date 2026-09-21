from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminPrincipal, CurrentPrincipal
from app.api.permissions import can_manage_clinic
from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.session import get_db
from app.models.clinic import ClinicStaff
from app.models.doctor import Doctor
from app.models.enums import ClinicStaffRole
from app.schemas.clinic import ClinicCreate, ClinicRead, ClinicUpdate
from app.schemas.common import PaginatedResponse
from app.schemas.payment import ConsultationFeeRead, ConsultationFeeUpdate
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
async def create_clinic(payload: ClinicCreate, _: AdminPrincipal, db: AsyncSession = Depends(get_db)) -> ClinicRead:
    return await clinic_service.create_clinic(db, payload)


@router.get("/{clinic_id}", response_model=ClinicRead)
async def get_clinic(clinic_id: UUID, db: AsyncSession = Depends(get_db)) -> ClinicRead:
    return await clinic_service.get_clinic(db, clinic_id)


@router.patch("/{clinic_id}", response_model=ClinicRead)
async def update_clinic(
    clinic_id: UUID, payload: ClinicUpdate, principal: CurrentPrincipal, db: AsyncSession = Depends(get_db)
) -> ClinicRead:
    """Admins edit any clinic; clinic admins edit their own clinics, but can't (de)activate them."""
    if not can_manage_clinic(principal, clinic_id):
        raise ForbiddenError("You can only edit clinics you manage")
    if not principal.is_admin and "is_active" in payload.model_fields_set:
        raise ForbiddenError("Only platform admins can change activation")
    return await clinic_service.update_clinic(db, clinic_id, payload)


@router.put("/{clinic_id}/doctors/{doctor_id}/fee", response_model=ConsultationFeeRead)
async def set_consultation_fee(
    clinic_id: UUID,
    doctor_id: UUID,
    payload: ConsultationFeeUpdate,
    principal: CurrentPrincipal,
    db: AsyncSession = Depends(get_db),
) -> ConsultationFeeRead:
    """
    A doctor's consultation fee at this clinic (admins and the clinic's
    admins). Null means the clinic confirms the price; then only "pay at
    clinic" is offered. Adds the doctor to the clinic's staff if needed.
    """
    if not can_manage_clinic(principal, clinic_id):
        raise ForbiddenError("You can only set fees at clinics you manage")
    await clinic_service.get_clinic(db, clinic_id)
    doctor = await db.get(Doctor, doctor_id)
    if doctor is None:
        raise NotFoundError(f"Doctor '{doctor_id}' not found")
    membership = await db.scalar(
        select(ClinicStaff).where(ClinicStaff.clinic_id == clinic_id, ClinicStaff.doctor_id == doctor_id)
    )
    if membership is None:
        membership = ClinicStaff(
            clinic_id=clinic_id, doctor_id=doctor_id, role=ClinicStaffRole.DOCTOR, full_name=doctor.full_name
        )
        db.add(membership)
    membership.consultation_fee = payload.consultation_fee
    await db.commit()
    return ConsultationFeeRead(clinic_id=clinic_id, doctor_id=doctor_id, consultation_fee=payload.consultation_fee)
