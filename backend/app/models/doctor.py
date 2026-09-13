import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Numeric, String, Text
from sqlalchemy import Boolean
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDPkMixin
from app.models.enums import VerificationStatus


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

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    specialty: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

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
