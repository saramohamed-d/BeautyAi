"""
Enum types shared across models.

Design decision: use Python `enum.Enum` + SQLAlchemy's `Enum(..., native_enum=True)`
so these become real Postgres ENUM types, not free-text/varchar columns.

Why: invalid values (e.g. a typo'd appointment status) are rejected by
the database itself on INSERT/UPDATE, not just by Pydantic validation at
the API boundary — a second line of defense, cheap to add now while the
schema is still small. The trade-off (documented so it isn't a surprise
later) is that adding a new enum value requires a migration
(`ALTER TYPE ... ADD VALUE`), unlike a varchar column. Given how
deliberately these value sets are chosen (they mirror explicit business
rules in the spec, e.g. risk_level low/medium/high), that trade-off is
worth it here.
"""

import enum


class Language(str, enum.Enum):
    AR = "ar"
    EN = "en"


class ConsentType(str, enum.Enum):
    DATA_PROCESSING = "data_processing"
    MEDICAL_ADVICE_DISCLAIMER = "medical_advice_disclaimer"
    MARKETING = "marketing"


class ConversationChannel(str, enum.Enum):
    WEB = "web"
    WHATSAPP = "whatsapp"


class ConversationStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ESCALATED = "escalated"


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class IntakeStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"


class VerificationStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class AuthTokenPurpose(str, enum.Enum):
    """What a one-time auth token is for (Sprint 17)."""

    PASSWORD_RESET = "password_reset"
    EMAIL_VERIFICATION = "email_verification"
    PHONE_VERIFICATION = "phone_verification"


class NotificationChannel(str, enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"


class NotificationStatus(str, enum.Enum):
    # Waiting for its send time (reminders are written the moment a
    # booking is made, and sent the day before).
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    # Nothing to send to: the person turned this channel off, or has no
    # address for it. Kept as a row so the history shows why.
    SKIPPED = "skipped"
    # The reason to send it disappeared (e.g. the appointment was cancelled).
    CANCELLED = "cancelled"


class DocumentType(str, enum.Enum):
    """Verification documents a doctor uploads (spec section 4, "Verification")."""

    MEDICAL_LICENSE = "medical_license"
    MEDICAL_DEGREE = "medical_degree"
    NATIONAL_ID = "national_id"
    SPECIALTY_CERTIFICATE = "specialty_certificate"


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ClinicStaffRole(str, enum.Enum):
    DOCTOR = "doctor"
    CLINIC_ADMIN = "clinic_admin"
    RECEPTION = "reception"


class AppointmentStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class EvidenceLevel(str, enum.Enum):
    SYSTEMATIC_REVIEW = "systematic_review"
    RCT = "rct"
    COHORT_STUDY = "cohort_study"
    EXPERT_OPINION = "expert_opinion"
    OFFICIAL_GUIDANCE = "official_guidance"


class KnowledgeDocumentStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    ARCHIVED = "archived"


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ActorType(str, enum.Enum):
    PATIENT = "patient"
    DOCTOR = "doctor"
    CLINIC_ADMIN = "clinic_admin"
    PLATFORM_ADMIN = "platform_admin"
    SYSTEM = "system"


class UserRole(str, enum.Enum):
    """
    The four roles from the product spec. The AI is deliberately NOT a
    role: it acts through backend tools on behalf of an authenticated
    user and inherits that user's permissions.
    """

    PATIENT = "patient"
    DOCTOR = "doctor"
    CLINIC_ADMIN = "clinic_admin"
    PLATFORM_ADMIN = "platform_admin"


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    # An account an admin must activate before its first login. Doctor
    # sign-up (Sprint 12) does NOT use it: doctors log in right away to
    # upload their documents; `doctors.verification_status` is what gates
    # being listed, taking bookings and publishing slots.
    PENDING = "pending"
    SUSPENDED = "suspended"


class PaymentMethod(str, enum.Enum):
    CARD = "card"
    WALLET = "wallet"  # mobile wallets (Vodafone Cash, etc.) through the gateway
    PAY_AT_CLINIC = "pay_at_clinic"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"  # checkout started; waiting for the gateway's webhook
    PAID = "paid"
    FAILED = "failed"
    EXPIRED = "expired"
    DUE_AT_CLINIC = "due_at_clinic"
    REFUND_PENDING = "refund_pending"  # refund requested, not yet confirmed
    REFUNDED = "refunded"
    NEEDS_REFUND = "needs_refund"  # money received but no appointment could be made; refund failed → admin

