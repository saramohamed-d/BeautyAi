import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDPkMixin
from app.models.enums import Language, NotificationChannel, NotificationStatus


class Notification(Base, UUIDPkMixin, TimestampMixin):
    """
    One message to one person on one channel (Sprint 15).

    Design decisions:

    - **Every message is a row, written before anything is sent.** A
      reminder for tomorrow is stored the moment the booking is made,
      with `scheduled_for` set; the sender picks up whatever is due. That
      makes what will be sent inspectable and cancellable (a cancelled
      appointment cancels its pending reminder) instead of living in a
      queue nobody can see.
    - **`dedupe_key` is unique.** It carries the reason for the message
      ("reminder:24h:<appointment id>"), so the same reminder can never
      be created — or sent — twice, however many times the booking code
      runs.
    - **The rendered subject and body are stored**, not just a template
      name: what we actually sent someone is part of the record, and
      templates change.
    - Channels a person has turned off still produce a row, with status
      `skipped`, so "why didn't they get an SMS?" is answerable.
    """

    __tablename__ = "notifications"

    # Who it's for. Both are nullable: a doctor has no patient profile,
    # and a patient may have no login.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="SET NULL"), nullable=True, index=True
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        SAEnum(NotificationChannel, name="notification_channel", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    status: Mapped[NotificationStatus] = mapped_column(
        SAEnum(NotificationStatus, name="notification_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=NotificationStatus.PENDING,
        index=True,
    )
    # Which message this is, e.g. "appointment_reminder" (app/notifications/templates.py).
    template: Mapped[str] = mapped_column(String(64), nullable=False)
    language: Mapped[Language] = mapped_column(
        SAEnum(Language, name="language", values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    # Email address or phone number, as it was when the message was written.
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # What the message was about, for the admin list and for cancelling.
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(nullable=False, default=0)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        # The sender's query: everything pending whose time has come.
        Index("ix_notifications_status_scheduled_for", "status", "scheduled_for"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Notification id={self.id} template={self.template!r} channel={self.channel.value}>"
