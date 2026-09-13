"""
Shared model mixins.

Design decision: `id`, `created_at`, and `updated_at` are defined ONCE here
and mixed into every model, instead of repeated on each table.

Why UUIDs generated in the database (gen_random_uuid(), from the pgcrypto
extension) rather than in Python (uuid4()):
- Atomic with the INSERT — no risk of a Python-generated ID never making
  it to the row if the process crashes between generation and insert.
- Works identically for rows written by any client (ORM, raw SQL, future
  data-migration scripts, seed scripts) without every writer needing to
  remember to generate an ID.
- UUIDs (vs. auto-increment integers) avoid leaking row counts/sequence
  info through IDs exposed in API responses (e.g. `/doctors/{id}`), and
  make it safe to generate IDs client-side later (e.g. idempotency keys)
  without coordinating with the database.

Why `onupdate=func.now()` for updated_at:
- Guarantees the timestamp is correct even if application code forgets
  to set it explicitly on an update — it's enforced at the ORM-flush
  level, not by convention.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class UUIDPkMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
