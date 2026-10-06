"""
Doctor sign-up and verification (Sprint 12; docs/verification.md).

The flow from the spec (section 4, "Verification"):

    registers → uploads documents → submits → admin approves / rejects

Design decisions:

- **Signing up gives a real login immediately, but no visibility.** A new
  doctor is `verification_status = pending` with `submitted_at = NULL`:
  they can log in, complete their profile and upload documents, but they
  are not listed in search, can't publish availability and can't be
  booked. Only an admin's approval changes that (`ensure_can_practise`).
- **Submitting requires the documents that justify a decision**: a
  medical licence and an ID. Without them there's nothing to review.
- **A rejection is not a dead end.** The admin's reason is stored on the
  doctor and shown to them; fixing the documents and submitting again
  puts the application back in the queue.
- Every decision is written to the audit trail with the admin's id.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationAppError
from app.core.logging import get_logger
from app.core.security import hash_password
from app.models.doctor import Doctor, DoctorDocument
from app.models.enums import DocumentStatus, DocumentType, UserRole, VerificationStatus
from app.models.user import User
from app.schemas.doctor import DoctorRegisterRequest, DocumentReview, VerificationDecision
from app.services import audit_service, notification_service
from app.services.auth_service import normalize_email, normalize_phone
from app.storage import files

logger = get_logger(__name__)

# Without these two there's nothing for an admin to check.
REQUIRED_DOCUMENTS = (DocumentType.MEDICAL_LICENSE, DocumentType.NATIONAL_ID)
MISSING_DOCUMENTS = "missing_documents"
ALREADY_SUBMITTED = "already_submitted"
NOT_VERIFIED = "doctor_not_verified"


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def register_doctor(db: AsyncSession, data: DoctorRegisterRequest) -> tuple[User, Doctor]:
    """Creates the login and the (unverified) doctor profile in one transaction."""
    email = normalize_email(data.email)
    phone = normalize_phone(data.phone)

    taken_user = await db.scalar(select(User).where(or_(User.email == email, User.phone == phone)))
    taken_doctor = await db.scalar(select(Doctor).where(Doctor.email == email))
    if taken_user is not None or taken_doctor is not None:
        field = "email" if (taken_doctor is not None or (taken_user and taken_user.email == email)) else "phone number"
        raise ConflictError(f"An account with this {field} already exists")

    user = User(email=email, phone=phone, password_hash=hash_password(data.password), role=UserRole.DOCTOR)
    db.add(user)
    await db.flush()

    doctor = Doctor(
        user_id=user.id,
        full_name=data.full_name,
        specialty=data.specialty,
        sub_specialty=data.sub_specialty,
        license_number=data.license_number,
        years_experience=data.years_experience,
        medical_degree=data.medical_degree,
        university=data.university,
        city=data.city,
        avatar=data.avatar,
        email=email,
        phone=phone,
        verification_status=VerificationStatus.PENDING,
    )
    db.add(doctor)
    await db.commit()
    await db.refresh(user)
    await db.refresh(doctor)
    logger.info("doctor.registered", doctor_id=str(doctor.id))
    return user, doctor


async def get_doctor_for_user(db: AsyncSession, user: User) -> Doctor | None:
    if user.role != UserRole.DOCTOR:
        return None
    return await db.scalar(select(Doctor).where(Doctor.user_id == user.id))


def ensure_can_practise(doctor: Doctor) -> None:
    """Guards everything patient-facing: slots, bookings, being listed."""
    if doctor.verification_status != VerificationStatus.VERIFIED or not doctor.is_active:
        raise ForbiddenError(
            "This doctor isn't verified yet, so appointments can't be published or booked", code=NOT_VERIFIED
        )


# --- Documents --------------------------------------------------------------------------


async def list_documents(db: AsyncSession, doctor_id: UUID) -> list[DoctorDocument]:
    rows = await db.scalars(
        select(DoctorDocument).where(DoctorDocument.doctor_id == doctor_id).order_by(DoctorDocument.created_at)
    )
    return list(rows.all())


async def get_document(db: AsyncSession, doctor_id: UUID, document_id: UUID) -> DoctorDocument:
    document = await db.get(DoctorDocument, document_id)
    if document is None or document.doctor_id != doctor_id:
        raise NotFoundError(f"Document '{document_id}' not found")
    return document


async def add_document(
    db: AsyncSession,
    *,
    doctor: Doctor,
    document_type: DocumentType,
    filename: str,
    stream,
    uploaded_by_user_id: UUID | None,
) -> DoctorDocument:
    """Stores one uploaded file (validated in app/storage/files.py) against the doctor."""
    if doctor.verification_status == VerificationStatus.VERIFIED:
        raise ConflictError("This doctor is already verified")
    relative_path, media_type, size = files.save_upload(stream, folder=f"doctors/{doctor.id}")
    document = DoctorDocument(
        doctor_id=doctor.id,
        document_type=document_type,
        original_filename=files.safe_filename(filename),
        stored_path=relative_path,
        content_type=media_type,
        size_bytes=size,
        uploaded_by_user_id=uploaded_by_user_id,
    )
    db.add(document)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        files.delete(relative_path)  # never leave an orphan file behind
        raise
    await db.refresh(document)
    logger.info("doctor.document_uploaded", doctor_id=str(doctor.id), document_type=document_type.value)
    return document


async def delete_document(db: AsyncSession, doctor: Doctor, document: DoctorDocument) -> None:
    if doctor.verification_status == VerificationStatus.VERIFIED:
        raise ConflictError("A verified doctor's documents can't be removed")
    stored_path = document.stored_path
    await db.delete(document)
    await db.commit()
    files.delete(stored_path)


async def review_document(db: AsyncSession, document: DoctorDocument, review: DocumentReview) -> DoctorDocument:
    document.status = review.status
    document.review_notes = review.review_notes
    await db.commit()
    await db.refresh(document)
    return document


# --- Application --------------------------------------------------------------------------


async def submit_application(db: AsyncSession, doctor: Doctor, *, actor: Principal | None = None) -> Doctor:
    """The doctor sends their application in for review."""
    if doctor.verification_status == VerificationStatus.VERIFIED:
        raise ConflictError("This application is already approved")
    if doctor.submitted_at is not None and doctor.verification_status == VerificationStatus.PENDING:
        raise ConflictError("This application is already being reviewed", code=ALREADY_SUBMITTED)

    uploaded = {document.document_type for document in await list_documents(db, doctor.id)}
    missing = [kind.value for kind in REQUIRED_DOCUMENTS if kind not in uploaded]
    if missing:
        raise ValidationAppError(
            "Please upload your medical licence and your ID before submitting", code=MISSING_DOCUMENTS
        )

    doctor.verification_status = VerificationStatus.PENDING
    doctor.submitted_at = _now()
    doctor.reviewed_at = None
    doctor.verification_notes = None
    audit_service.record(
        db, actor=actor, action="doctor.application_submitted", resource_type="doctor", resource_id=doctor.id
    )
    await db.commit()
    await db.refresh(doctor)
    logger.info("doctor.application_submitted", doctor_id=str(doctor.id))
    return doctor


async def review_application(
    db: AsyncSession, doctor: Doctor, decision: VerificationDecision, *, actor: Principal
) -> Doctor:
    """A platform admin approves or rejects; the reason is kept and shown to the doctor."""
    if doctor.submitted_at is None:
        raise ConflictError("This doctor hasn't submitted an application yet")

    doctor.verification_status = decision.status
    doctor.reviewed_at = _now()
    doctor.reviewed_by_user_id = actor.user.id
    doctor.verification_notes = (decision.notes or "").strip() or None
    if decision.status == VerificationStatus.REJECTED:
        # Back to the doctor: fixing the documents and submitting again re-queues it.
        doctor.submitted_at = None
    await notification_service.on_doctor_decision(
        db, doctor, verified=decision.status == VerificationStatus.VERIFIED
    )
    audit_service.record(
        db,
        actor=actor,
        action=f"doctor.{decision.status.value}",
        resource_type="doctor",
        resource_id=doctor.id,
        extra={"notes": doctor.verification_notes},
    )
    await db.commit()
    await db.refresh(doctor)
    logger.info("doctor.reviewed", doctor_id=str(doctor.id), status=decision.status.value)
    return doctor


async def list_applications(
    db: AsyncSession, page: int, page_size: int, *, status: VerificationStatus | None = None, submitted_only: bool = True
) -> tuple[list[Doctor], int]:
    """The admin review queue: submitted applications, oldest first (longest wait first)."""
    query = select(Doctor)
    if submitted_only:
        query = query.where(Doctor.submitted_at.is_not(None))
    if status is not None:
        query = query.where(Doctor.verification_status == status)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = await db.scalars(
        query.order_by(Doctor.submitted_at.asc()).offset((page - 1) * page_size).limit(page_size)
    )
    return list(rows.all()), total or 0


async def document_counts(db: AsyncSession, doctor_ids: list[UUID]) -> dict[UUID, int]:
    if not doctor_ids:
        return {}
    rows = await db.execute(
        select(DoctorDocument.doctor_id, func.count())
        .where(DoctorDocument.doctor_id.in_(doctor_ids))
        .group_by(DoctorDocument.doctor_id)
    )
    return {doctor_id: count for doctor_id, count in rows}


__all__ = [
    "ALREADY_SUBMITTED",
    "MISSING_DOCUMENTS",
    "NOT_VERIFIED",
    "REQUIRED_DOCUMENTS",
    "DocumentStatus",
    "add_document",
    "delete_document",
    "document_counts",
    "ensure_can_practise",
    "get_doctor_for_user",
    "get_document",
    "list_applications",
    "list_documents",
    "register_doctor",
    "review_application",
    "review_document",
    "submit_application",
]
