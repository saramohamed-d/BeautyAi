"""
Platform admin API (Sprint 14; docs/admin.md).

Everything here requires the platform_admin role. The screens it backs
also use endpoints that already existed: the doctor verification queue
(Sprint 12), payments (Sprint 11), safety events (Sprint 7) and the
knowledge review list (Sprint 8) — this module adds the platform-wide
report, user administration and the audit log.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminPrincipal
from app.db.session import get_db
from app.models.enums import NotificationChannel, NotificationStatus, UserRole, UserStatus
from app.payments.gateways import PaymentGateway, get_gateway
from app.notifications.providers import Notifier, get_notifier
from app.schemas.admin import (
    AdminOverview,
    AdminUserRead,
    AuditEventRead,
    DispatchResult,
    NotificationRead,
    RefundRequest,
    UserStatusUpdate,
)
from app.schemas.common import PaginatedResponse
from app.schemas.payment import PaymentRead
from app.services import admin_service, notification_service, payment_service

router = APIRouter(prefix="/admin", tags=["platform admin"])


@router.get("/overview", response_model=AdminOverview)
async def overview(_: AdminPrincipal, db: AsyncSession = Depends(get_db)) -> AdminOverview:
    """People, verification, bookings, money, and what needs a human today."""
    return AdminOverview(**await admin_service.overview(db))


@router.get("/users", response_model=PaginatedResponse[AdminUserRead])
async def list_users(
    _: AdminPrincipal,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: UserRole | None = Query(None),
    status_filter: UserStatus | None = Query(None, alias="status"),
    q: str | None = Query(None, max_length=100, description="Part of an email address or phone number"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[AdminUserRead]:
    rows, total = await admin_service.list_users(db, page, page_size, role=role, status=status_filter, q=q)
    items = [
        AdminUserRead.model_validate(user, from_attributes=True).model_copy(
            update={"full_name": full_name, "last_login_at": user.last_login_at}
        )
        for user, full_name in rows
    ]
    return PaginatedResponse.build(items, total, page, page_size)


@router.patch("/users/{user_id}", response_model=AdminUserRead)
async def set_user_status(
    user_id: UUID, payload: UserStatusUpdate, principal: AdminPrincipal, db: AsyncSession = Depends(get_db)
) -> AdminUserRead:
    """
    Suspends or restores a login. Suspending also ends its open sessions.
    An admin can't change their own status (409 `cannot_suspend_self`).
    """
    user = await admin_service.set_user_status(
        db, user_id, payload.status, actor=principal, reason=payload.reason
    )
    full_name = await admin_service.display_name(db, user)
    return AdminUserRead.model_validate(user, from_attributes=True).model_copy(update={"full_name": full_name})


@router.post("/payments/{payment_id}/refund", response_model=PaymentRead)
async def refund_payment(
    payment_id: UUID,
    payload: RefundRequest,
    principal: AdminPrincipal,
    db: AsyncSession = Depends(get_db),
    gateway: PaymentGateway = Depends(get_gateway),
) -> PaymentRead:
    """
    Refunds a payment by hand: the "needs refund" pile, or a goodwill
    refund. 409 `payment_not_refundable` if no money was taken.
    """
    payment = await admin_service.retry_refund(
        db, payment_id, gateway=gateway, actor=principal, reason=payload.reason
    )
    data = PaymentRead.model_validate(payment, from_attributes=True)
    return data.model_copy(update={"status": payment_service.display_status(payment)})


@router.get("/audit-events", response_model=PaginatedResponse[AuditEventRead])
async def list_audit_events(
    _: AdminPrincipal,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    action: str | None = Query(None, max_length=128, description="Prefix, e.g. `doctor.` or `user.`"),
    resource_type: str | None = Query(None, max_length=64),
    resource_id: UUID | None = Query(None),
    actor_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[AuditEventRead]:
    """The append-only record of what administrators did, newest first."""
    items, total = await admin_service.list_audit_events(
        db, page, page_size, action=action, resource_type=resource_type, resource_id=resource_id, actor_id=actor_id
    )
    return PaginatedResponse.build(items, total, page, page_size)


@router.get("/notifications", response_model=PaginatedResponse[NotificationRead])
async def list_notifications(
    _: AdminPrincipal,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status_filter: NotificationStatus | None = Query(None, alias="status"),
    channel: NotificationChannel | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[NotificationRead]:
    """Every message the platform has written, newest scheduled first."""
    items, total = await notification_service.list_notifications(
        db, page, page_size, status=status_filter, channel=channel
    )
    return PaginatedResponse.build(items, total, page, page_size)


@router.post("/notifications/dispatch", response_model=DispatchResult)
async def dispatch_notifications(
    _: AdminPrincipal, db: AsyncSession = Depends(get_db), notifier: Notifier = Depends(get_notifier)
) -> DispatchResult:
    """
    Sends everything that's due now, instead of waiting for the scheduled
    run (`python -m app.notifications.cli run`). Safe to press twice.
    """
    return DispatchResult(**await notification_service.dispatch_due(db, notifier))
