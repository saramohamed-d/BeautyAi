from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ActorType, NotificationChannel, NotificationStatus, UserRole, UserStatus
from app.schemas.auth import UserRead


class AdminUserRead(UserRead):
    """A login plus the name from whichever profile it owns."""

    full_name: str | None = None
    last_login_at: datetime | None = None


class UserStatusUpdate(BaseModel):
    status: UserStatus
    # Why, for the audit trail; shown to nobody but admins.
    reason: str | None = Field(None, max_length=500)


class AuditEventRead(BaseModel):
    id: UUID
    actor_type: ActorType
    actor_id: UUID | None
    action: str
    resource_type: str
    resource_id: UUID | None
    extra_data: dict | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RefundRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


# --- Reports ------------------------------------------------------------------------------


class UsersReport(BaseModel):
    total: int
    by_role: dict[str, int]
    suspended: int
    new_this_month: int


class DoctorsReport(BaseModel):
    by_status: dict[str, int]
    awaiting_review: int


class ClinicsReport(BaseModel):
    total: int
    active: int


class AppointmentsReport(BaseModel):
    by_status: dict[str, int]
    upcoming: int


class PaymentsReport(BaseModel):
    paid_total: Decimal
    paid_this_month: Decimal
    refunded_total: Decimal
    due_at_clinic: int
    needs_refund: int


class AttentionReport(BaseModel):
    """What an admin has to act on, and the badge counts in the dashboard."""

    doctor_applications: int
    safety_events: int
    knowledge_review: int
    documents_pending: int
    needs_refund: int


class DailyPoint(BaseModel):
    date: date
    bookings: int
    revenue: Decimal


class AdminOverview(BaseModel):
    users: UsersReport
    doctors: DoctorsReport
    clinics: ClinicsReport
    appointments: AppointmentsReport
    payments: PaymentsReport
    attention: AttentionReport
    # The last 14 clinic-local days.
    daily: list[DailyPoint]


class RoleCount(BaseModel):
    role: UserRole
    count: int


# --- Notifications (Sprint 15) --------------------------------------------------------------


class NotificationRead(BaseModel):
    id: UUID
    channel: NotificationChannel
    status: NotificationStatus
    template: str
    language: str
    recipient: str
    subject: str | None
    body: str
    patient_id: UUID | None
    appointment_id: UUID | None
    scheduled_for: datetime
    sent_at: datetime | None
    attempts: int
    provider: str | None
    error: str | None

    model_config = ConfigDict(from_attributes=True)


class DispatchResult(BaseModel):
    sent: int
    failed: int
