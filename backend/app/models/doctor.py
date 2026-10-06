import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy import Boolean
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDPkMixin
from app.models.enums import DocumentStatus, DocumentType, VerificationStatus


class Doctor(Base, UUIDPkMixin, TimestampMixin):
    """
    A doctor profile. Verification is deliberately separate from
    credentials: `verification_status` is the admin's overall yes/no
    decision (Sprint 16 - Admin doctor verification), while
    `doctor_credentials` holds the individual documents/licenses that
    justify that decision — the two are related but distinct, so an
    admin can see *why* a doctor is (not) verified.

    `rating` is a denormalized average, written by a background job in a
    later sprint (never computed inline from reviews in the hot request
    path) — Sprint 1 just reserves the column.
    """

    __tablename__ = "doctors"

    # Login identity for the doctor's own dashboard (roadmap Sprint 12).
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), unique=True, nullable=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    specialty: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # Sprint 12 sign-up fields (spec section 4, "Suggested Fields").
    sub_specialty: Mapped[str | None] = mapped_column(String(255), nullable=True)
    license_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    medical_degree: Mapped[str | None] = mapped_column(String(255), nullable=True)
    university: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Key of an illustrated avatar drawn by the frontend, e.g. "woman-2"; null = neutral default.
    avatar: Mapped[str | None] = mapped_column(String(32), nullable=True)
    years_experience: Mapped[int | None] = mapped_column(nullable=True)
    rating: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(
            VerificationStatus,
            name="verification_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=VerificationStatus.PENDING,
        index=True,
    )
    # Null until the doctor submits their application; set again on every
    # resubmission after a rejection, so admins see the newest first.
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # The admin's reason, shown to the doctor when rejected.
    verification_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    documents: Mapped[list["DoctorDocument"]] = relationship(
        back_populates="doctor", cascade="all, delete-orphan"
    )
    credentials: Mapped[list["DoctorCredential"]] = relationship(
        back_populates="doctor", cascade="all, delete-orphan"
    )
    clinic_memberships: Mapped[list["ClinicStaff"]] = relationship(back_populates="doctor")
    doctor_procedures: Mapped[list["DoctorProcedure"]] = relationship(back_populates="doctor")
    availability_slots: Mapped[list["Availability"]] = relationship(back_populates="doctor")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="doctor")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Doctor id={self.id} name={self.full_name!r}>"


class DoctorCredential(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "doctor_credentials"

    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False
    )
    credential_type: Mapped[str] = mapped_column(String(64), nullable=False)
    issuing_authority: Mapped[str] = mapped_column(String(255), nullable=False)
    credential_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    document_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    doctor: Mapped["Doctor"] = relationship(back_populates="credentials")

    __table_args__ = (Index("ix_doctor_credentials_doctor_id", "doctor_id"),)


class DoctorDocument(Base, UUIDPkMixin, TimestampMixin):
    """
    A verification document (licence, degree, ID, certificate).

    The file itself is NOT in the database and is never served from a
    guessable URL: it's written under `UPLOAD_DIR` with a random name,
    and `GET /doctors/{id}/documents/{doc_id}/file` streams it only to
    the doctor who owns it or a platform admin. `original_filename` is
    kept only to show the doctor what they uploaded.
    """

    __tablename__ = "doctor_documents"

    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_type: Mapped[DocumentType] = mapped_column(
        SAEnum(DocumentType, name="document_type", values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(DocumentStatus, name="document_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=DocumentStatus.PENDING,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    # Path relative to UPLOAD_DIR, so the storage root can move between environments.
    stored_path: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    doctor: Mapped["Doctor"] = relationship(back_populates="documents")
