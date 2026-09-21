"""
Platform admin operations (Sprint 14; docs/admin.md).

What the platform team needs to run the business: who is on it, which
doctors are waiting to be verified, what the money is doing, and a
record of what administrators did.

Design decisions:

- **Nothing here is a new source of truth.** The figures are read from
  the same tables the rest of the app writes; the doctor queue is the
  Sprint 12 API, the payment list is Sprint 11's. This module adds the
  platform-wide *view* and the two actions that only belong to a
  platform admin: suspending a login and retrying a stuck refund.
- **Suspending ends the sessions.** A suspended user is refused at login
  (`ensure_can_sign_in`), and their refresh tokens are revoked here, so
  an open browser tab can't keep renewing an access token.
- **An admin can't suspend themself** — that locks the platform out of
  its own dashboard with no way back through the UI.
- **Every admin action is audited** with the admin's id (`audit_events`),
  because "who turned this off?" must be answerable months later.
"""

from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, literal_column, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal
from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.models.audit import AuditEvent, SafetyEvent
from app.models.clinic import Clinic, ClinicStaff
from app.models.doctor import Doctor
from app.models.enums import (
    AppointmentStatus,
    KnowledgeDocumentStatus,
    PaymentStatus,
    UserRole,
    UserStatus,
    VerificationStatus,
)
from app.models.knowledge import KnowledgeDocument
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.scheduling import Appointment
from app.models.user import RefreshToken, User
from app.payments.gateways import PaymentGateway
from app.services import audit_service, payment_service

logger = get_logger(__name__)

SELF_SUSPEND = "cannot_suspend_self"
NOT_REFUNDABLE = "payment_not_refundable"
# Money that has actually been taken; what a refund could still apply to.
REFUNDABLE = (PaymentStatus.PAID, PaymentStatus.NEEDS_REFUND, PaymentStatus.REFUND_PENDING)
REPORT_DAYS = 14


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _tz() -> ZoneInfo:
    return ZoneInfo(get_settings().clinic_timezone)


# --- Users ------------------------------------------------------------------------------


async def list_users(
    db: AsyncSession,
    page: int,
    page_size: int,
    *,
    role: UserRole | None = None,
    status: UserStatus | None = None,
    q: str | None = None,
) -> tuple[list[tuple[User, str | None]], int]:
    """Logins with the display name from whichever profile they own."""
    query = select(User)
    if role is not None:
        query = query.where(User.role == role)
    if status is not None:
        query = query.where(User.status == status)
    if q:
        term = f"%{q.strip().lower()}%"
        query = query.where(or_(func.lower(User.email).like(term), User.phone.like(term)))

    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = await db.scalars(
        query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    users = list(rows.all())
    return [(user, name) for user, name in zip(users, await _display_names(db, users), strict=True)], total


async def display_name(db: AsyncSession, user: User) -> str | None:
    """The name to show for one login (patient, doctor or staff profile)."""
    return (await _display_names(db, [user]))[0]


async def _display_names(db: AsyncSession, users: list[User]) -> list[str | None]:
    """One lookup per profile table rather than one per user."""
    if not users:
        return []
    ids = [user.id for user in users]
    names: dict[UUID, str] = {}
    for model in (Patient, Doctor):
        rows = await db.execute(select(model.user_id, model.full_name).where(model.user_id.in_(ids)))
        names.update({user_id: full_name for user_id, full_name in rows if user_id})
    # Clinic admins have no profile of their own; use their staff membership.
    rows = await db.execute(
        select(ClinicStaff.user_id, ClinicStaff.full_name).where(ClinicStaff.user_id.in_(ids))
    )
    for user_id, full_name in rows:
        names.setdefault(user_id, full_name)
    return [names.get(user.id) for user in users]


async def set_user_status(
    db: AsyncSession, user_id: UUID, status: UserStatus, *, actor: Principal, reason: str | None = None
) -> User:
    """Suspends or restores a login. Suspending also ends its open sessions."""
    user = await db.get(User, user_id)
    if user is None:
        raise NotFoundError(f"User '{user_id}' not found")
    if user.id == actor.user.id:
        raise ConflictError("You can't change your own account's status", code=SELF_SUSPEND)

    user.status = status
    if status != UserStatus.ACTIVE:
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=_now())
        )
    audit_service.record(
        db,
        actor=actor,
        action=f"user.{status.value}",
        resource_type="user",
        resource_id=user.id,
        extra={"reason": reason} if reason else None,
    )
    await db.commit()
    await db.refresh(user)
    logger.info("admin.user_status_changed", user_id=str(user.id), status=status.value)
    return user


# --- Payments ------------------------------------------------------------------------------


async def retry_refund(
    db: AsyncSession, payment_id: UUID, *, gateway: PaymentGateway, actor: Principal, reason: str
) -> Payment:
    """
    Refunds a payment by hand: the "needs refund" pile when the gateway
    refused an automatic refund, or a goodwill refund for a paid booking.
    """
    payment = await db.get(Payment, payment_id)
    if payment is None:
        raise NotFoundError(f"Payment '{payment_id}' not found")
    if payment.status not in REFUNDABLE:
        raise ConflictError(
            f"A '{payment.status.value}' payment can't be refunded", code=NOT_REFUNDABLE
        )
    await payment_service.refund(db, payment, gateway, reason)
    audit_service.record(
        db,
        actor=actor,
        action="payment.refund_requested",
        resource_type="payment",
        resource_id=payment.id,
        extra={"reason": reason, "outcome": payment.status.value},
    )
    await db.commit()
    await db.refresh(payment)
    return payment


# --- Audit log ------------------------------------------------------------------------------


async def list_audit_events(
    db: AsyncSession,
    page: int,
    page_size: int,
    *,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    actor_id: UUID | None = None,
) -> tuple[list[AuditEvent], int]:
    query = select(AuditEvent)
    if action:
        query = query.where(AuditEvent.action.like(f"{action}%"))
    if resource_type:
        query = query.where(AuditEvent.resource_type == resource_type)
    if resource_id:
        query = query.where(AuditEvent.resource_id == resource_id)
    if actor_id:
        query = query.where(AuditEvent.actor_id == actor_id)
    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = await db.scalars(
        query.order_by(AuditEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return list(rows.all()), total


# --- Reports ------------------------------------------------------------------------------


async def _count(db: AsyncSession, model, *conditions) -> int:
    return await db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0


async def _grouped(db: AsyncSession, column, *conditions) -> dict[str, int]:
    rows = await db.execute(select(column, func.count()).where(*conditions).group_by(column))
    return {(key.value if hasattr(key, "value") else str(key)): count for key, count in rows}


async def _money(db: AsyncSession, *conditions) -> Decimal:
    total = await db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(*conditions))
    return Decimal(total or 0)


async def overview(db: AsyncSession, *, now: datetime | None = None) -> dict:
    """The platform's figures: people, verification, bookings, money, and what needs attention."""
    now = now or _now()
    month_ago = now - timedelta(days=30)

    users_by_role = await _grouped(db, User.role)
    return {
        "users": {
            "total": sum(users_by_role.values()),
            "by_role": users_by_role,
            "suspended": await _count(db, User, User.status == UserStatus.SUSPENDED),
            "new_this_month": await _count(db, User, User.created_at >= month_ago),
        },
        "doctors": {
            "by_status": await _grouped(db, Doctor.verification_status),
            # The queue an admin actually works through.
            "awaiting_review": await _count(
                db,
                Doctor,
                Doctor.submitted_at.is_not(None),
                Doctor.verification_status == VerificationStatus.PENDING,
            ),
        },
        "clinics": {
            "total": await _count(db, Clinic),
            "active": await _count(db, Clinic, Clinic.is_active.is_(True)),
        },
        "appointments": {
            "by_status": await _grouped(db, Appointment.status, Appointment.created_at >= month_ago),
            "upcoming": await _count(
                db,
                Appointment,
                Appointment.scheduled_start >= now,
                Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]),
            ),
        },
        "payments": {
            "paid_total": await _money(db, Payment.status == PaymentStatus.PAID),
            "paid_this_month": await _money(
                db, Payment.status == PaymentStatus.PAID, Payment.paid_at >= month_ago
            ),
            "refunded_total": await _money(db, Payment.status == PaymentStatus.REFUNDED),
            "due_at_clinic": await _count(db, Payment, Payment.status == PaymentStatus.DUE_AT_CLINIC),
            # The pile that needs a human: refunds the gateway refused.
            "needs_refund": await _count(db, Payment, Payment.status == PaymentStatus.NEEDS_REFUND),
        },
        "attention": {
            "doctor_applications": await _count(
                db,
                Doctor,
                Doctor.submitted_at.is_not(None),
                Doctor.verification_status == VerificationStatus.PENDING,
            ),
            "safety_events": await _count(
                db, SafetyEvent, SafetyEvent.requires_human.is_(True), SafetyEvent.resolved.is_(False)
            ),
            "knowledge_review": await _count(
                db, KnowledgeDocument, KnowledgeDocument.status == KnowledgeDocumentStatus.PENDING_REVIEW
            ),
            "documents_pending": await _count(db, Doctor, Doctor.verification_status == VerificationStatus.PENDING),
            "needs_refund": await _count(db, Payment, Payment.status == PaymentStatus.NEEDS_REFUND),
        },
        "daily": await _daily(db, now),
    }


async def _daily(db: AsyncSession, now: datetime) -> list[dict]:
    """Bookings and money taken per day for the last two weeks, in clinic-local days."""
    tz = _tz()
    start_local = datetime.combine((now.astimezone(tz) - timedelta(days=REPORT_DAYS - 1)).date(), time.min, tz)
    start = start_local.astimezone(timezone.utc)
    zone = get_settings().clinic_timezone

    def local_day(column):
        return func.date(func.timezone(zone, column))

    # GROUP BY 1 (the selected day): repeating the expression would send the
    # time zone as a second bound parameter, which Postgres won't match.
    by_selected_day = literal_column("1")

    bookings = {
        str(day): count
        for day, count in await db.execute(
            select(local_day(Appointment.created_at), func.count())
            .where(Appointment.created_at >= start)
            .group_by(by_selected_day)
        )
    }
    revenue = {
        str(day): Decimal(total or 0)
        for day, total in await db.execute(
            select(local_day(Payment.paid_at), func.coalesce(func.sum(Payment.amount), 0))
            .where(Payment.paid_at >= start, Payment.status.in_([PaymentStatus.PAID, PaymentStatus.REFUNDED]))
            .group_by(by_selected_day)
        )
    }
    days = []
    for offset in range(REPORT_DAYS):
        day = (start_local + timedelta(days=offset)).date().isoformat()
        days.append({"date": day, "bookings": bookings.get(day, 0), "revenue": revenue.get(day, Decimal(0))})
    return days
