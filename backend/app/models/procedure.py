import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDPkMixin


class Procedure(Base, UUIDPkMixin, TimestampMixin):
    """
    A catalog entry for a procedure/service (e.g. "Botox", "Chemical Peel").

    This is the *catalog* definition — generic info and a typical price
    range. Doctor- and clinic-specific pricing/availability lives in
    `doctor_procedures`, not here, so the catalog doesn't need a new row
    every time a clinic changes its price.
    """

    __tablename__ = "procedures"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    category: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    typical_price_min: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    typical_price_max: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)

    doctor_procedures: Mapped[list["DoctorProcedure"]] = relationship(back_populates="procedure")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Procedure id={self.id} slug={self.slug!r}>"


class DoctorProcedure(Base, UUIDPkMixin, TimestampMixin):
    """
    The N:N edge between doctors and procedures, scoped per clinic.

    Why scoped per clinic: the same doctor can offer the same procedure
    at different clinics for different prices (different overheads,
    equipment, etc.) — a plain doctor<->procedure join table couldn't
    represent that. This table is exactly what Sprint 11's matching
    engine and Sprint 13's availability screen will query.
    """

    __tablename__ = "doctor_procedures"

    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False
    )
    procedure_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("procedures.id", ondelete="CASCADE"), nullable=False
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False
    )
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EGP")

    doctor: Mapped["Doctor"] = relationship(back_populates="doctor_procedures")
    procedure: Mapped["Procedure"] = relationship(back_populates="doctor_procedures")
    clinic: Mapped["Clinic"] = relationship(back_populates="doctor_procedures")

    __table_args__ = (
        UniqueConstraint(
            "doctor_id", "procedure_id", "clinic_id", name="uq_doctor_procedure_clinic"
        ),
        CheckConstraint("price >= 0", name="ck_doctor_procedures_price_non_negative"),
    )
