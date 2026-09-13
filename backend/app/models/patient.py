import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDPkMixin
from app.models.enums import ConsentType, Language


class Patient(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "patients"

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Phone is the primary identifier for patients in this market (WhatsApp-first,
    # per the roadmap's Sprint 17). Unique + indexed since it's the main lookup key.
    phone: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    preferred_language: Mapped[Language] = mapped_column(
        SAEnum(Language, name="language", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=Language.AR,
        server_default=Language.AR.value,
    )

    consents: Mapped[list["PatientConsent"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="patient")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="patient")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"<Patient id={self.id} phone={self.phone!r}>"


class PatientConsent(Base, UUIDPkMixin, TimestampMixin):
    """
    Records a patient's grant (or revocation) of a specific consent type.

    Design decision: consents are append-only rows, not a single
    boolean column on `patients`. Each grant/revoke is its own row with
    its own timestamp and the version of the consent text shown, so we
    always have a full, auditable history of what the patient agreed to
    and when — required for the "explicit consent" and "configurable
    retention" requirements in the security spec.
    """

    __tablename__ = "patient_consents"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    consent_type: Mapped[ConsentType] = mapped_column(
        SAEnum(ConsentType, name="consent_type", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    consent_text_version: Mapped[str] = mapped_column(String(32), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="consents")

    __table_args__ = (
        Index("ix_patient_consents_patient_id_type", "patient_id", "consent_type"),
    )
