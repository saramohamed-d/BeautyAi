"""
Re-exports every model so that importing `app.models` registers all
tables on `Base.metadata` — required for Alembic autogenerate (see
alembic/env.py) and convenient for the rest of the app / seed scripts.
"""

from app.models.audit import AuditEvent, SafetyEvent
from app.models.clinic import Clinic, ClinicStaff
from app.models.conversation import Conversation, Intake, Message
from app.models.doctor import Doctor, DoctorCredential
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.models.patient import Patient, PatientConsent
from app.models.procedure import DoctorProcedure, Procedure
from app.models.scheduling import Appointment, Availability

__all__ = [
    "AuditEvent",
    "SafetyEvent",
    "Clinic",
    "ClinicStaff",
    "Conversation",
    "Intake",
    "Message",
    "Doctor",
    "DoctorCredential",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "Patient",
    "PatientConsent",
    "DoctorProcedure",
    "Procedure",
    "Appointment",
    "Availability",
]
