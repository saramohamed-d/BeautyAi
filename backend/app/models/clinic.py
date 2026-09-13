import uuid

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDPkMixin
from app.models.enums import ClinicStaffRole


class Clinic(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "clinics"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    city: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(128), nullable=False, default="Egypt")
    # Stored as separate lat/lng columns (not PostGIS) — Sprint 1 scope is
    # "location" as a simple filter field. A geospatial type/index is only
    # worth the added dependency once Sprint 11/13 need real proximity
    # search; flagged here rather than silently deferred.
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    staff: Mapped[list["ClinicStaff"]] = relationship(
        back_populates="clinic", cascade="all, delete-orphan"
    )
    doctor_procedures: Mapped[list["DoctorProcedure"]] = relationship(back_populates="clinic")
    availability_slots: Mapped[list["Availability"]] = relationship(back_populates="clinic")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="clinic")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Clinic id={self.id} name={self.name!r}>"


class ClinicStaff(Base, UUIDPkMixin, TimestampMixin):
    """
    Membership of a person at a clinic.

    Design decision: `doctor_id` is nullable because a staff row can
    represent a non-doctor employee (clinic admin, receptionist) who
    doesn't have a `doctors` profile. When `role == DOCTOR`, `doctor_id`
    is expected to be set (enforced in the service layer in Sprint 2,
    since a DB-level conditional constraint here would be premature —
    there's no `users` table yet to link non-doctor staff to, so
    `full_name`/`email` carry their identity directly for now).
    """

    __tablename__ = "clinic_staff"

    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False
    )
    doctor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doctors.id", ondelete="CASCADE"), nullable=True
    )
    role: Mapped[ClinicStaffRole] = mapped_column(
        SAEnum(
            ClinicStaffRole, name="clinic_staff_role", values_callable=lambda e: [m.value for m in e]
        ),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    clinic: Mapped["Clinic"] = relationship(back_populates="staff")
    doctor: Mapped["Doctor | None"] = relationship(back_populates="clinic_memberships")

    __table_args__ = (
        UniqueConstraint("clinic_id", "doctor_id", name="uq_clinic_staff_clinic_doctor"),
    )
