import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDPkMixin
from app.models.enums import AuthTokenPurpose


class AuthToken(Base, UUIDPkMixin, TimestampMixin):
    """
    A one-time token: a password-reset link, or a code that proves someone
    owns an email address or phone number (Sprint 17).

    Design decisions:

    - **Only the hash is stored**, exactly like refresh tokens: a stolen
      database dump can't be used to reset anyone's password.
    - **Single use and short-lived.** `used_at` is set the moment it's
      accepted, and every other unused token for the same purpose is
      revoked with it, so an old link in an inbox stops working.
    - **`attempts`** caps guessing of the 6-digit verification codes; a
      reset link is long enough that guessing isn't the threat.
    - `sent_to` records the address the token went to, which may differ
      from the account's current one (that's the point, for verification).
    """

    __tablename__ = "auth_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    purpose: Mapped[AuthTokenPurpose] = mapped_column(
        SAEnum(AuthTokenPurpose, name="auth_token_purpose", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    sent_to: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (Index("ix_auth_tokens_user_purpose", "user_id", "purpose"),)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuthToken purpose={self.purpose.value} user_id={self.user_id}>"
