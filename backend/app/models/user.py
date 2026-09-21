import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDPkMixin
from app.models.enums import UserRole, UserStatus


class User(Base, UUIDPkMixin, TimestampMixin):
    """
    A login identity. One central table for all four roles (spec §7).

    Design decisions:
    - Role-specific data stays in the profile tables (`patients`,
      `doctors`, `clinic_staff`), each linked back here by `user_id`.
      `users` only holds what authentication needs, so a profile can
      exist without a login (e.g. a walk-in patient a clinic registers)
      and a login's role is never inferred from which profile exists.
    - Email and phone are both optional but at least one is required
      (CHECK constraint); either can be used to log in. Email is stored
      lower-cased by the service layer so uniqueness is case-insensitive.
    - `email_verified_at` / `phone_verified_at` are recorded but not yet
      enforced: sending verification emails/SMS needs the notification
      providers from roadmap Sprint 15.
    """

    __tablename__ = "users"

    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        index=True,
    )
    status: Mapped[UserStatus] = mapped_column(
        SAEnum(UserStatus, name="user_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=UserStatus.ACTIVE,
        server_default=UserStatus.ACTIVE.value,
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    phone_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("email IS NOT NULL OR phone IS NOT NULL", name="ck_users_email_or_phone"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} role={self.role.value}>"


class RefreshToken(Base, UUIDPkMixin):
    """
    A long-lived refresh token, stored only as a SHA-256 hash.

    Rotation with reuse detection: every refresh marks the presented
    token `used_at` and issues a new one in the same `family_id` (one
    family = one login on one device). Presenting a used token again
    means someone replayed a stolen copy, so the whole family is revoked.

    Exception: a token used within the last few seconds (the reuse grace
    period in auth_service) may be exchanged again. Two tabs reloading at
    once, or a retried request, legitimately send the same token twice;
    without the grace period that would log the user out.

    `revoked_at` means dead for good: set on logout, on detected reuse,
    and never cleared.
    """

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")

    __table_args__ = (
        Index("ix_refresh_tokens_user_id", "user_id"),
        Index("ix_refresh_tokens_family_id", "family_id"),
    )
