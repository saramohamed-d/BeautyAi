"""
Audit trail (`audit_events`).

Sprint 12 starts writing it for decisions a person needs to be able to
justify later: who verified or rejected a doctor, and why. Sprint 14
adds the admin screen that reads it.

The rows are append-only and keep no foreign keys (see
`app/models/audit.py`), so an entry survives the record it describes.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal
from app.models.audit import AuditEvent
from app.models.enums import ActorType, UserRole

_ACTOR_BY_ROLE = {
    UserRole.PATIENT: ActorType.PATIENT,
    UserRole.DOCTOR: ActorType.DOCTOR,
    UserRole.CLINIC_ADMIN: ActorType.CLINIC_ADMIN,
    UserRole.PLATFORM_ADMIN: ActorType.PLATFORM_ADMIN,
}


def record(
    db: AsyncSession,
    *,
    actor: Principal | None,
    action: str,
    resource_type: str,
    resource_id: UUID | None,
    extra: dict | None = None,
) -> AuditEvent:
    """Adds an audit row to the caller's transaction (committed with it)."""
    event = AuditEvent(
        actor_type=_ACTOR_BY_ROLE.get(actor.role, ActorType.SYSTEM) if actor else ActorType.SYSTEM,
        actor_id=actor.user.id if actor else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        extra_data=extra,
    )
    db.add(event)
    return event
