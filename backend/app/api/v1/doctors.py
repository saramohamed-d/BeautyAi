from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminPrincipal, CurrentPrincipal, OptionalPrincipal, Principal
from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.session import get_db
from app.models.doctor import Doctor, DoctorDocument
from app.models.enums import DocumentType, VerificationStatus
from app.schemas.common import PaginatedResponse
from app.schemas.doctor import (
    DoctorApplication,
    DoctorCreate,
    DoctorDocumentRead,
    DoctorRead,
    DoctorSearchResult,
    DoctorUpdate,
    DocumentReview,
    VerificationDecision,
)
from app.services import doctor_service, doctor_verification_service
from app.services.doctor_service import SearchSort
from app.storage import files

router = APIRouter(prefix="/doctors", tags=["doctors"])

# Fields only a platform admin may change: a doctor must never be able to
# verify or re-activate themself.
ADMIN_ONLY_FIELDS = {"verification_status", "is_active"}


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


@router.get("/search", response_model=PaginatedResponse[DoctorSearchResult])
async def search_doctors(
    principal: OptionalPrincipal,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    q: str | None = Query(None, max_length=100, description="Text in the doctor's name or specialty"),
    specialty: str | None = Query(None, max_length=255),
    city: str | None = Query(None, max_length=128),
    procedure_id: UUID | None = Query(None, description="Only doctors offering this procedure"),
    max_price: float | None = Query(None, ge=0, description="Max price (EGP) for the procedure, or any procedure"),
    available_before: datetime | None = Query(None, description="Only doctors with a bookable slot starting before this"),
    verified_only: bool = Query(True),
    sort: SearchSort = Query("soonest"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[DoctorSearchResult]:
    """Public doctor search with next available slot, starting price and clinics. Declared before /{doctor_id}."""
    items, total = await doctor_service.search_doctors(
        db, page, page_size, q=q, specialty=specialty, city=city, procedure_id=procedure_id, max_price=max_price,
        available_before=available_before, verified_only=verified_only, sort=sort,
        for_patient_id=principal.patient_id if principal else None,
    )
    return PaginatedResponse.build(items, total, page, page_size)


@router.get("/applications", response_model=PaginatedResponse[DoctorApplication])
async def list_applications(
    _: AdminPrincipal,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: VerificationStatus | None = Query(VerificationStatus.PENDING, alias="status"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[DoctorApplication]:
    """
    The admin review queue: doctors who have submitted an application,
    the ones waiting longest first, each with their documents.
    """
    doctors, total = await doctor_verification_service.list_applications(db, page, page_size, status=status_filter)
    items = [
        DoctorApplication(
            doctor=DoctorRead.model_validate(doctor, from_attributes=True),
            documents=[
                DoctorDocumentRead.model_validate(document, from_attributes=True)
                for document in await doctor_verification_service.list_documents(db, doctor.id)
            ],
        )
        for doctor in doctors
    ]
    return PaginatedResponse.build(items, total, page, page_size)


@router.post("", response_model=DoctorRead, status_code=status.HTTP_201_CREATED)
async def create_doctor(payload: DoctorCreate, _: AdminPrincipal, db: AsyncSession = Depends(get_db)) -> DoctorRead:
    return await doctor_service.create_doctor(db, payload)


@router.get("/{doctor_id}", response_model=DoctorRead)
async def get_doctor(doctor_id: UUID, db: AsyncSession = Depends(get_db)) -> DoctorRead:
    return await doctor_service.get_doctor(db, doctor_id)


@router.patch("/{doctor_id}", response_model=DoctorRead)
async def update_doctor(
    doctor_id: UUID, payload: DoctorUpdate, principal: CurrentPrincipal, db: AsyncSession = Depends(get_db)
) -> DoctorRead:
    """Admins edit any doctor; a doctor edits their own profile, except verification and activation."""
    if not principal.is_admin:
        if principal.doctor_id != doctor_id:
            raise ForbiddenError("You can only edit your own profile")
        if ADMIN_ONLY_FIELDS & payload.model_fields_set:
            raise ForbiddenError("Only platform admins can change verification or activation")
    return await doctor_service.update_doctor(db, doctor_id, payload)


# --- Verification (Sprint 12; docs/verification.md) --------------------------------------


async def _own_doctor(db: AsyncSession, principal: Principal, doctor_id: UUID) -> Doctor:
    """The doctor themself or a platform admin; anyone else gets 404, as elsewhere."""
    doctor = await db.get(Doctor, doctor_id)
    if doctor is None or not (principal.is_admin or principal.doctor_id == doctor_id):
        raise NotFoundError(f"Doctor '{doctor_id}' not found")
    return doctor


@router.get("/{doctor_id}/documents", response_model=list[DoctorDocumentRead])
async def list_documents(
    doctor_id: UUID, principal: CurrentPrincipal, db: AsyncSession = Depends(get_db)
) -> list[DoctorDocument]:
    """The doctor's own verification documents (or any doctor's, for an admin)."""
    await _own_doctor(db, principal, doctor_id)
    return await doctor_verification_service.list_documents(db, doctor_id)


@router.post("/{doctor_id}/documents", response_model=DoctorDocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    doctor_id: UUID,
    principal: CurrentPrincipal,
    document_type: DocumentType = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> DoctorDocument:
    """
    Uploads one verification document (PDF or image, up to MAX_UPLOAD_MB).
    The type is taken from the file's own bytes, not its name or headers.
    """
    doctor = await _own_doctor(db, principal, doctor_id)
    return await doctor_verification_service.add_document(
        db,
        doctor=doctor,
        document_type=document_type,
        filename=file.filename or "document",
        stream=file.file,
        uploaded_by_user_id=principal.user.id,
    )


@router.get("/{doctor_id}/documents/{document_id}/file", response_class=FileResponse)
async def download_document(
    doctor_id: UUID, document_id: UUID, principal: CurrentPrincipal, db: AsyncSession = Depends(get_db)
) -> FileResponse:
    """Streams the stored file to its owner or an admin. Never a public URL."""
    await _own_doctor(db, principal, doctor_id)
    document = await doctor_verification_service.get_document(db, doctor_id, document_id)
    path = files.resolve(document.stored_path)
    if not path.is_file():
        raise NotFoundError("The stored file is missing")
    return FileResponse(
        path,
        media_type=document.content_type,
        filename=document.original_filename,
        content_disposition_type="attachment",
    )


@router.delete("/{doctor_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doctor_id: UUID, document_id: UUID, principal: CurrentPrincipal, db: AsyncSession = Depends(get_db)
) -> None:
    doctor = await _own_doctor(db, principal, doctor_id)
    document = await doctor_verification_service.get_document(db, doctor_id, document_id)
    await doctor_verification_service.delete_document(db, doctor, document)


@router.patch("/{doctor_id}/documents/{document_id}", response_model=DoctorDocumentRead)
async def review_document(
    doctor_id: UUID,
    document_id: UUID,
    payload: DocumentReview,
    _: AdminPrincipal,
    db: AsyncSession = Depends(get_db),
) -> DoctorDocument:
    """Admins mark a single document accepted or rejected while reviewing."""
    document = await doctor_verification_service.get_document(db, doctor_id, document_id)
    return await doctor_verification_service.review_document(db, document, payload)


@router.post("/{doctor_id}/submit", response_model=DoctorRead)
async def submit_application(
    doctor_id: UUID, principal: CurrentPrincipal, db: AsyncSession = Depends(get_db)
) -> Doctor:
    """
    The doctor sends their application for review. Needs a medical licence
    and an ID on file (422 `missing_documents` otherwise).
    """
    doctor = await _own_doctor(db, principal, doctor_id)
    return await doctor_verification_service.submit_application(db, doctor, actor=principal)


@router.post("/{doctor_id}/verification", response_model=DoctorRead)
async def review_application(
    doctor_id: UUID, payload: VerificationDecision, principal: AdminPrincipal, db: AsyncSession = Depends(get_db)
) -> Doctor:
    """Platform admin: approve or reject. A rejection must say why; both are audited."""
    doctor = await db.get(Doctor, doctor_id)
    if doctor is None:
        raise NotFoundError(f"Doctor '{doctor_id}' not found")
    return await doctor_verification_service.review_application(db, doctor, payload, actor=principal)
