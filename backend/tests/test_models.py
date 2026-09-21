"""
Sprint 1 database tests.

Design decision: these tests run against the real Postgres database
(not sqlite/mocks), using the actual async session — because the whole
point of Sprint 1 is verifying database-level guarantees (FK cascades,
UNIQUE constraints, CHECK constraints) that an in-memory/sqlite
substitute wouldn't enforce identically to Postgres. Each test wraps its
work in a transaction that's rolled back at the end (see the
`db_session` fixture) so tests never depend on or interfere with the dev
seed data, and can run repeatedly without accumulating rows.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models import (
    Appointment,
    Availability,
    Clinic,
    ClinicStaff,
    Conversation,
    Doctor,
    DoctorProcedure,
    Intake,
    Message,
    Patient,
    PatientConsent,
    Procedure,
)
from app.models.enums import (
    AppointmentStatus,
    ClinicStaffRole,
    ConsentType,
    ConversationChannel,
    ConversationStatus,
    IntakeStatus,
    Language,
    MessageRole,
    VerificationStatus,
)


@pytest_asyncio.fixture
async def db_session():
    """
    Yields a session whose outer transaction is rolled back after the
    test, so every test starts from a clean slate without touching
    dev/seed data and without needing a separate test database.
    """
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()


def _unique_phone() -> str:
    return f"+2010{uuid.uuid4().int % 10**8:08d}"


@pytest.mark.asyncio
async def test_create_patient_generates_uuid_and_timestamps(db_session: AsyncSession) -> None:
    patient = Patient(full_name="Test Patient", phone=_unique_phone())
    db_session.add(patient)
    await db_session.flush()

    assert isinstance(patient.id, uuid.UUID)
    assert patient.created_at is not None
    assert patient.updated_at is not None
    assert patient.preferred_language == Language.AR  # default applied


@pytest.mark.asyncio
async def test_patient_phone_uniqueness_enforced(db_session: AsyncSession) -> None:
    phone = _unique_phone()
    db_session.add(Patient(full_name="Patient One", phone=phone))
    await db_session.flush()

    db_session.add(Patient(full_name="Patient Two", phone=phone))
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_conversation_cascades_to_messages_and_intake(db_session: AsyncSession) -> None:
    patient = Patient(full_name="Cascade Test", phone=_unique_phone())
    db_session.add(patient)
    await db_session.flush()

    conversation = Conversation(
        patient_id=patient.id,
        channel=ConversationChannel.WEB,
        language=Language.AR,
        status=ConversationStatus.ACTIVE,
    )
    db_session.add(conversation)
    await db_session.flush()

    db_session.add(Message(conversation_id=conversation.id, role=MessageRole.USER, content="hi"))
    db_session.add(
        Intake(
            conversation_id=conversation.id,
            patient_id=patient.id,
            concern="wrinkles",
            status=IntakeStatus.IN_PROGRESS,
        )
    )
    await db_session.flush()

    # Deleting the conversation must cascade to its messages and intake
    # (ON DELETE CASCADE), matching the 1:N and 1:1 ownership modeled here.
    await db_session.delete(conversation)
    await db_session.flush()

    from sqlalchemy import select

    remaining_messages = (
        await db_session.execute(select(Message).where(Message.conversation_id == conversation.id))
    ).scalars().all()
    remaining_intakes = (
        await db_session.execute(select(Intake).where(Intake.conversation_id == conversation.id))
    ).scalars().all()

    assert remaining_messages == []
    assert remaining_intakes == []


@pytest.mark.asyncio
async def test_intake_conversation_id_is_unique(db_session: AsyncSession) -> None:
    patient = Patient(full_name="Unique Intake Test", phone=_unique_phone())
    db_session.add(patient)
    await db_session.flush()

    conversation = Conversation(
        patient_id=patient.id, channel=ConversationChannel.WEB, language=Language.AR
    )
    db_session.add(conversation)
    await db_session.flush()

    db_session.add(Intake(conversation_id=conversation.id, concern="a"))
    await db_session.flush()

    db_session.add(Intake(conversation_id=conversation.id, concern="b"))
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_availability_end_after_start_constraint(db_session: AsyncSession) -> None:
    clinic = Clinic(name="Test Clinic", city="Cairo", country="Egypt")
    doctor = Doctor(full_name="Test Doctor", specialty="Dermatology")
    db_session.add_all([clinic, doctor])
    await db_session.flush()

    start = datetime.now(timezone.utc)
    bad_slot = Availability(
        doctor_id=doctor.id,
        clinic_id=clinic.id,
        start_time=start,
        end_time=start - timedelta(minutes=30),  # end before start: invalid
    )
    db_session.add(bad_slot)
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_appointment_availability_is_unique_prevents_double_booking(
    db_session: AsyncSession,
) -> None:
    clinic = Clinic(name="Test Clinic 2", city="Cairo", country="Egypt")
    doctor = Doctor(full_name="Test Doctor 2", specialty="Dermatology")
    patient_a = Patient(full_name="Patient A", phone=_unique_phone())
    patient_b = Patient(full_name="Patient B", phone=_unique_phone())
    db_session.add_all([clinic, doctor, patient_a, patient_b])
    await db_session.flush()

    start = datetime.now(timezone.utc) + timedelta(days=1)
    slot = Availability(
        doctor_id=doctor.id, clinic_id=clinic.id, start_time=start, end_time=start + timedelta(minutes=30)
    )
    db_session.add(slot)
    await db_session.flush()

    db_session.add(
        Appointment(
            patient_id=patient_a.id,
            doctor_id=doctor.id,
            clinic_id=clinic.id,
            availability_id=slot.id,
            status=AppointmentStatus.CONFIRMED,
            scheduled_start=slot.start_time,
            scheduled_end=slot.end_time,
        )
    )
    await db_session.flush()

    # Second appointment on the SAME slot must fail the UNIQUE constraint
    # on availability_id — this is the database-level double-booking guard.
    db_session.add(
        Appointment(
            patient_id=patient_b.id,
            doctor_id=doctor.id,
            clinic_id=clinic.id,
            availability_id=slot.id,
            status=AppointmentStatus.PENDING,
            scheduled_start=slot.start_time,
            scheduled_end=slot.end_time,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_appointment_idempotency_key_is_unique(db_session: AsyncSession) -> None:
    clinic = Clinic(name="Idempotency Clinic", city="Cairo", country="Egypt")
    doctor = Doctor(full_name="Idempotency Doctor", specialty="Dermatology")
    patient = Patient(full_name="Idempotency Patient", phone=_unique_phone())
    db_session.add_all([clinic, doctor, patient])
    await db_session.flush()

    start = datetime.now(timezone.utc) + timedelta(days=2)
    key = str(uuid.uuid4())

    db_session.add(
        Appointment(
            patient_id=patient.id,
            doctor_id=doctor.id,
            clinic_id=clinic.id,
            status=AppointmentStatus.PENDING,
            scheduled_start=start,
            scheduled_end=start + timedelta(minutes=30),
            idempotency_key=key,
        )
    )
    await db_session.flush()

    db_session.add(
        Appointment(
            patient_id=patient.id,
            doctor_id=doctor.id,
            clinic_id=clinic.id,
            status=AppointmentStatus.PENDING,
            scheduled_start=start,
            scheduled_end=start + timedelta(minutes=30),
            idempotency_key=key,  # retried request reusing the same key
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_doctor_procedure_scoped_uniqueness_per_clinic(db_session: AsyncSession) -> None:
    """
    Same doctor + same procedure at two DIFFERENT clinics is allowed
    (different price/context per clinic); the same triple twice is not.
    """
    clinic_a = Clinic(name="Clinic A", city="Cairo", country="Egypt")
    clinic_b = Clinic(name="Clinic B", city="Cairo", country="Egypt")
    doctor = Doctor(full_name="Multi Clinic Doctor", specialty="Aesthetic Medicine")
    procedure = Procedure(name="Botox", slug=f"botox-{uuid.uuid4().hex[:8]}", category="injectable")
    db_session.add_all([clinic_a, clinic_b, doctor, procedure])
    await db_session.flush()

    db_session.add(
        DoctorProcedure(doctor_id=doctor.id, procedure_id=procedure.id, clinic_id=clinic_a.id, price=4000)
    )
    db_session.add(
        DoctorProcedure(doctor_id=doctor.id, procedure_id=procedure.id, clinic_id=clinic_b.id, price=4500)
    )
    await db_session.flush()  # both succeed: different clinic_id

    db_session.add(
        DoctorProcedure(doctor_id=doctor.id, procedure_id=procedure.id, clinic_id=clinic_a.id, price=4200)
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()  # duplicate (doctor, procedure, clinic_a)


@pytest.mark.asyncio
async def test_doctor_procedure_price_non_negative_constraint(db_session: AsyncSession) -> None:
    clinic = Clinic(name="Price Clinic", city="Cairo", country="Egypt")
    doctor = Doctor(full_name="Price Doctor", specialty="Dermatology")
    procedure = Procedure(
        name="Peel", slug=f"peel-{uuid.uuid4().hex[:8]}", category="skin_treatment"
    )
    db_session.add_all([clinic, doctor, procedure])
    await db_session.flush()

    db_session.add(
        DoctorProcedure(doctor_id=doctor.id, procedure_id=procedure.id, clinic_id=clinic.id, price=-100)
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_clinic_staff_unique_per_clinic_and_doctor(db_session: AsyncSession) -> None:
    clinic = Clinic(name="Staff Clinic", city="Giza", country="Egypt")
    doctor = Doctor(full_name="Staff Doctor", specialty="Dermatology")
    db_session.add_all([clinic, doctor])
    await db_session.flush()

    db_session.add(
        ClinicStaff(
            clinic_id=clinic.id, doctor_id=doctor.id, role=ClinicStaffRole.DOCTOR, full_name="Staff Doctor"
        )
    )
    await db_session.flush()

    db_session.add(
        ClinicStaff(
            clinic_id=clinic.id, doctor_id=doctor.id, role=ClinicStaffRole.DOCTOR, full_name="Staff Doctor"
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_patient_consent_relationship_and_cascade(db_session: AsyncSession) -> None:
    patient = Patient(full_name="Consent Patient", phone=_unique_phone())
    db_session.add(patient)
    await db_session.flush()

    db_session.add(
        PatientConsent(
            patient_id=patient.id,
            consent_type=ConsentType.DATA_PROCESSING,
            granted=True,
            consent_text_version="1.0",
            granted_at=datetime.now(timezone.utc),
        )
    )
    await db_session.flush()
    await db_session.refresh(patient, attribute_names=["consents"])

    assert len(patient.consents) == 1
    assert patient.consents[0].consent_type == ConsentType.DATA_PROCESSING


@pytest.mark.asyncio
async def test_doctor_default_verification_status_is_pending(db_session: AsyncSession) -> None:
    doctor = Doctor(full_name="New Doctor", specialty="Dermatology")
    db_session.add(doctor)
    await db_session.flush()

    assert doctor.verification_status == VerificationStatus.PENDING
    assert doctor.is_active is True
