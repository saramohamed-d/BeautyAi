"""
Re-exports every model so that importing `app.models` registers all
tables on `Base.metadata` — required for Alembic autogenerate (see
alembic/env.py) and convenient for the rest of the app / seed scripts.
"""

from app.models.audit import AuditEvent, SafetyEvent
from app.models.auth_token import AuthToken
from app.models.clinic import Clinic, ClinicHours, ClinicStaff
from app.models.conversation import Conversation, Intake, Message
from app.models.doctor import Doctor, DoctorCredential, DoctorDocument
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.models.notification import Notification
from app.models.patient import Patient, PatientConsent
from app.models.payment import Payment, PaymentEvent
from app.models.procedure import DoctorProcedure, Procedure
from app.models.scheduling import Appointment, Availability
from app.models.user import RefreshToken, User

__all__ = [
    "AuditEvent",
    "AuthToken",
    "SafetyEvent",
    "Clinic",
    "ClinicHours",
    "ClinicStaff",
    "Conversation",
    "Intake",
    "Message",
    "Doctor",
    "DoctorCredential",
    "DoctorDocument",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "Notification",
    "Patient",
    "PatientConsent",
    "Payment",
    "PaymentEvent",
    "DoctorProcedure",
    "Procedure",
    "Appointment",
    "Availability",
    "RefreshToken",
    "User",
]
