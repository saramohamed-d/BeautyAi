import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDPkMixin
from app.models.enums import ActorType, RiskLevel


class AuditEvent(Base, UUIDPkMixin):
    """
    Append-only audit log entry.

    Design decision: deliberately NO foreign keys to the entities it
    describes. `resource_type` + `resource_id` reference *any* table
    generically (a `patient`, a `doctor`, an `appointment`, a
    `knowledge_document`, ...). A real FK would require either a
    different audit table per resource type (defeats having one log) or
    a polymorphic-association hack that most databases (Postgres
    included) don't support cleanly. The cost is that `resource_id`
    can't be validated at the DB layer and rows survive even if the
    referenced entity is later deleted — which is actually desirable for
    an audit trail (you want the log entry "appointment X was cancelled"
    to persist even after appointment X itself is purged by a retention
    policy).

    No `updated_at`: audit rows are immutable, like `messages`.
    """

    __tablename__ = "audit_events"

    actor_type: Mapped[ActorType] = mapped_column(
        SAEnum(ActorType, name="actor_type", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    extra_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_audit_events_resource_type_resource_id", "resource_type", "resource_id"),
        Index("ix_audit_events_actor_type_actor_id", "actor_type", "actor_id"),
        Index("ix_audit_events_created_at", "created_at"),
    )


class SafetyEvent(Base, UUIDPkMixin, TimestampMixin):
    """
    A record produced by the Safety Agent (Sprint 7) whenever it flags a
    conversation as medium/high risk.

    Both `conversation_id` and `patient_id` are nullable: a safety event
    can be raised before a patient is identified, and (rarely) might need
    to be created without an active conversation (e.g. a manually-logged
    admin escalation). `resolved`/`resolved_at` track the human-in-the-loop
    handoff required by the spec ("potentially dangerous or uncertain
    cases must be escalated to a qualified clinician").
    """

    __tablename__ = "safety_events"

    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="SET NULL"), nullable=True
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        SAEnum(RiskLevel, name="risk_level", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    red_flags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    requires_human: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    conversation: Mapped["Conversation | None"] = relationship(back_populates="safety_events")

    __table_args__ = (
        Index("ix_safety_events_risk_level", "risk_level"),
        Index("ix_safety_events_requires_human", "requires_human"),
    )
