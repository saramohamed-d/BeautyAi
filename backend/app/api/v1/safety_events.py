from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminPrincipal
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.audit import SafetyEvent
from app.models.enums import RiskLevel
from app.schemas.common import PaginatedResponse
from app.schemas.safety import SafetyEventRead, SafetyEventUpdate

# Escalations raised by the chat's safety screen or by the model. Admins
# review them here until the admin dashboard exists (Sprint 14).
router = APIRouter(prefix="/safety-events", tags=["safety"])


@router.get("", response_model=PaginatedResponse[SafetyEventRead])
async def list_safety_events(
    _: AdminPrincipal,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    requires_human: bool | None = Query(None),
    resolved: bool | None = Query(None),
    risk_level: RiskLevel | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[SafetyEventRead]:
    query = select(SafetyEvent)
    if requires_human is not None:
        query = query.where(SafetyEvent.requires_human == requires_human)
    if resolved is not None:
        query = query.where(SafetyEvent.resolved == resolved)
    if risk_level is not None:
        query = query.where(SafetyEvent.risk_level == risk_level)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = await db.scalars(query.order_by(SafetyEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    return PaginatedResponse.build(list(rows.all()), total or 0, page, page_size)


@router.patch("/{event_id}", response_model=SafetyEventRead)
async def update_safety_event(
    event_id: UUID, payload: SafetyEventUpdate, _: AdminPrincipal, db: AsyncSession = Depends(get_db)
) -> SafetyEventRead:
    event = await db.get(SafetyEvent, event_id)
    if event is None:
        raise NotFoundError(f"Safety event '{event_id}' not found")
    if payload.resolved is not None:
        event.resolved = payload.resolved
        event.resolved_at = datetime.now(timezone.utc) if payload.resolved else None
    if "notes" in payload.model_fields_set:
        event.notes = payload.notes
    await db.commit()
    await db.refresh(event)
    return event
