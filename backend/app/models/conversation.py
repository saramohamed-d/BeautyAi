import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDPkMixin
from app.models.enums import (
    ConversationChannel,
    ConversationStatus,
    IntakeStatus,
    Language,
    MessageRole,
)


class Conversation(Base, UUIDPkMixin, TimestampMixin):
    """
    A single chat session (web widget or WhatsApp thread).

    `patient_id` is nullable: a conversation can start before we know who
    the patient is (anonymous visitor on the landing page chat). It gets
    linked once the patient authenticates or completes intake far enough
    to be identified — that linking logic belongs to Sprint 6, not here.
    """

    __tablename__ = "conversations"

    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="SET NULL"), nullable=True
    )
    channel: Mapped[ConversationChannel] = mapped_column(
        SAEnum(
            ConversationChannel,
            name="conversation_channel",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=ConversationChannel.WEB,
    )
    language: Mapped[Language] = mapped_column(
        SAEnum(Language, name="language", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=Language.AR,
    )
    status: Mapped[ConversationStatus] = mapped_column(
        SAEnum(
            ConversationStatus,
            name="conversation_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=ConversationStatus.ACTIVE,
    )

    patient: Mapped["Patient | None"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    intake: Mapped["Intake | None"] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", uselist=False
    )
    safety_events: Mapped[list["SafetyEvent"]] = relationship(back_populates="conversation")

    __table_args__ = (Index("ix_conversations_patient_id", "patient_id"),)


class Message(Base, UUIDPkMixin):
    """
    A single turn in a conversation.

    Design decision: no `updated_at` here (only `created_at`, added
    manually rather than via TimestampMixin) — messages are immutable
    once written. This is a deliberate signal in the schema itself: the
    ORM has no `onupdate` hook for this table, so accidentally mutating a
    past message's content is unsupported by the model shape.

    `extra_data` (JSONB) carries structured payloads attached to a
    message — e.g. the extracted intake fields from Sprint 6, or a
    safety-agent verdict from Sprint 7 — without needing a new column (or
    new table) for every future structured-output type.
    """

    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[MessageRole] = mapped_column(
        SAEnum(MessageRole, name="message_role", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    extra_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    __table_args__ = (
        Index("ix_messages_conversation_id_created_at", "conversation_id", "created_at"),
    )


class Intake(Base, UUIDPkMixin, TimestampMixin):
    """
    Structured output of the Intake Agent (Sprint 6) for one conversation.

    Design decision: 1:1 with `conversation`, enforced with a UNIQUE
    constraint on `conversation_id` rather than a separate join table —
    a conversation produces at most one intake record, which the Intake
    Agent updates in place as it extracts more fields across turns.

    `structured_data`/`missing_fields` are JSONB because the exact set of
    extractable fields (concern, body_area, goal, severity, duration, ...)
    is an evolving, agent-defined shape (see the Intake Agent spec) —
    forcing it into fixed columns now would mean a migration every time
    the extraction schema grows in Sprint 6.
    """

    __tablename__ = "intakes"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="SET NULL"), nullable=True
    )
    concern: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body_area: Mapped[str | None] = mapped_column(String(255), nullable=True)
    goal: Mapped[str | None] = mapped_column(String(255), nullable=True)
    structured_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    missing_fields: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[IntakeStatus] = mapped_column(
        SAEnum(IntakeStatus, name="intake_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=IntakeStatus.IN_PROGRESS,
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="intake")
