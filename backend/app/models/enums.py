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
    SUPER_ADMIN = "super_admin"
    SYSTEM = "system"
