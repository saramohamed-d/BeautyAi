"""
Development seed data.

Design decision: this is a plain async script (`python -m app.db.seed`),
not a pytest fixture and not baked into a migration. Migrations should
only ever contain schema changes — mixing in data makes them harder to
reason about and impossible to safely re-run. Seed data is a separate,
idempotent-ish concern: this script wipes and re-inserts a fixed set of
rows every time it runs, which is exactly what's wanted for a local dev
database, and exactly wrong for a migration.

The data below is realistic for the target market (Cairo/Giza aesthetic
& dermatology clinics, Egyptian Arabic patient names and phone formats)
so that Sprint 4's chat UI and Sprint 11's matching engine have
believable data to develop against, without needing real patient data.
"""

import asyncio
import shutil
import uuid
from datetime import date, datetime, time, timedelta, timezone
from io import BytesIO

from sqlalchemy import delete

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.rag.embeddings import get_embedder
from app.rag.ingest import default_knowledge_dir, ingest_directory
from app.db.session import AsyncSessionLocal
from app.storage.files import save_upload, upload_root
from app.models import (
    Appointment,
    AuditEvent,
    Notification,
    Availability,
    Clinic,
    ClinicHours,
    ClinicStaff,
    Conversation,
    Doctor,
    DoctorCredential,
    DoctorDocument,
    DoctorProcedure,
    Intake,
    KnowledgeChunk,
    KnowledgeDocument,
    Message,
    Patient,
    PatientConsent,
    Payment,
    PaymentEvent,
    Procedure,
    RefreshToken,
    SafetyEvent,
    User,
)
from app.models.enums import (
    AppointmentStatus,
    DocumentType,
    ClinicStaffRole,
    ConsentType,
    ConversationChannel,
    ConversationStatus,
    IntakeStatus,
    Language,
    MessageRole,
    RiskLevel,
    UserRole,
    VerificationStatus,
)

configure_logging()
logger = get_logger(__name__)

NOW = datetime.now(timezone.utc)

# Every seeded login shares this password. Local development only — the
# script refuses to run outside APP_ENV=local/test (see seed()).
DEV_PASSWORD = "beautyai-dev-2026"
# The knowledge articles are editorial drafts; locally they're approved under
# this label so the chat can use them. It's shown on every article page.
DEV_REVIEWER = "Development sample — not clinically reviewed"

DEV_ACCOUNTS = [
    ("platform_admin", "admin@beautyai.example.com"),
    ("doctor", "dr.amira.hassan@example.com"),
    ("doctor (application awaiting review)", "dr.mona.elsherif@example.com"),
    ("clinic_admin", "yasmin.adel@newlook-zamalek.example.com"),
    ("patient", "nour.mohamed@example.com  (or +201555001122)"),
    ("patient", "omar.abdelrahman@example.com  (or +201555003344)"),
]


async def clear_all(session) -> None:
    """
    Delete in child-to-parent order so FK constraints don't block the
    wipe. Only used for local/dev re-seeding — never run against a
    database with real patient data.
    """
    for model in [
        # Audit rows have no foreign keys, so they don't block the wipe —
        # but a re-seeded dev database shouldn't keep a log of records that
        # no longer exist.
        AuditEvent,
        Notification,
        SafetyEvent,
        ClinicHours,
        DoctorDocument,
        PaymentEvent,
        Payment,
        Appointment,
        Availability,
        DoctorProcedure,
        DoctorCredential,
        ClinicStaff,
        KnowledgeChunk,
        KnowledgeDocument,
        Intake,
        Message,
        Conversation,
        PatientConsent,
        Procedure,
        Doctor,
        Clinic,
        Patient,
        RefreshToken,
        User,
    ]:
        await session.execute(delete(model))
    await session.commit()
    # Uploaded documents belong to the rows we just deleted; drop the files too,
    # so re-seeding doesn't leave orphans behind in UPLOAD_DIR.
    shutil.rmtree(upload_root() / "doctors", ignore_errors=True)


async def seed() -> None:
    app_env = get_settings().app_env
    if app_env not in ("local", "test"):
        raise SystemExit(f"Refusing to seed: this wipes every table, and APP_ENV is '{app_env}'.")

    async with AsyncSessionLocal() as session:
        logger.info("seed.clearing_existing_data")
        await clear_all(session)

        # --- Login accounts, one per role (see DEV_ACCOUNTS) ---
        password_hash = hash_password(DEV_PASSWORD)

        def dev_user(role: UserRole, email: str, phone: str | None = None) -> User:
            return User(email=email, phone=phone, password_hash=password_hash, role=role)

        user_admin = dev_user(UserRole.PLATFORM_ADMIN, "admin@beautyai.example.com")
        user_amira = dev_user(UserRole.DOCTOR, "dr.amira.hassan@example.com")
        user_mona = dev_user(UserRole.DOCTOR, "dr.mona.elsherif@example.com")
        user_yasmin = dev_user(UserRole.CLINIC_ADMIN, "yasmin.adel@newlook-zamalek.example.com")
        user_nour = dev_user(UserRole.PATIENT, "nour.mohamed@example.com", "+201555001122")
        user_omar = dev_user(UserRole.PATIENT, "omar.abdelrahman@example.com", "+201555003344")
        session.add_all([user_admin, user_amira, user_mona, user_yasmin, user_nour, user_omar])
        await session.flush()

        # --- Clinics ---
        clinic_zamalek = Clinic(
            name="عيادة نيو لوك للتجميل - الزمالك",
            description="عيادة متخصصة في طب التجميل والجلدية، تقدم خدمات الليزر والحقن التجميلي.",
            address="26 يوليو، الزمالك",
            city="Cairo",
            country="Egypt",
            latitude=30.0626,
            longitude=31.2197,
            phone="+201001234567",
            email="info@newlook-zamalek.example.com",
        )
        clinic_maadi = Clinic(
            name="مركز درملايف الجلدي - المعادي",
            description="مركز متخصص في الأمراض الجلدية والتجميل الطبي.",
            address="شارع 9، المعادي",
            city="Cairo",
            country="Egypt",
            latitude=29.9602,
            longitude=31.2569,
            phone="+201009876543",
            email="contact@dermalife-maadi.example.com",
        )
        clinic_sheikh_zayed = Clinic(
            name="كلينيك جلو - الشيخ زايد",
            description="عيادة تجميل حديثة متخصصة في العناية بالبشرة والحقن التجميلي.",
            address="محور 26 يوليو، الشيخ زايد",
            city="Giza",
            country="Egypt",
            latitude=30.0131,
            longitude=30.9756,
            phone="+201112223344",
            email="hello@glowclinic-sz.example.com",
        )
        session.add_all([clinic_zamalek, clinic_maadi, clinic_sheikh_zayed])
        await session.flush()

        # --- Opening hours (Sunday-Thursday, the Egyptian working week) ---
        # What the clinic dashboard generates bookable times from (Sprint 13).
        for clinic, (opens, closes) in (
            (clinic_zamalek, (time(10, 0), time(18, 0))),
            (clinic_maadi, (time(11, 0), time(20, 0))),
            (clinic_sheikh_zayed, (time(9, 0), time(17, 0))),
        ):
            session.add_all(
                [
                    ClinicHours(clinic_id=clinic.id, weekday=weekday, opens_at=opens, closes_at=closes)
                    for weekday in (6, 0, 1, 2, 3)  # Sunday-Thursday
                ]
            )

        # --- Doctors ---
        dr_amira = Doctor(
            user_id=user_amira.id,
            full_name="د. أميرة حسن",
            avatar="woman-3",
            specialty="Dermatology",
            bio="استشارية الأمراض الجلدية والتجميل، خبرة 12 عامًا في علاجات الليزر وحقن الفيلر.",
            years_experience=12,
            rating=4.8,
            phone="+201234567890",
            email="dr.amira.hassan@example.com",
            verification_status=VerificationStatus.VERIFIED,
        )
        dr_khaled = Doctor(
            full_name="د. خالد إبراهيم",
            avatar="man-1",
            specialty="Aesthetic Medicine",
            bio="أخصائي طب التجميل، متخصص في البوتوكس وشد الوجه بدون جراحة.",
            years_experience=8,
            rating=4.6,
            phone="+201234567891",
            email="dr.khaled.ibrahim@example.com",
            verification_status=VerificationStatus.VERIFIED,
        )
        dr_mona = Doctor(
            user_id=user_mona.id,
            full_name="د. منى الشريف",
            avatar="woman-1",
            specialty="Dermatology",
            bio="أخصائية جلدية، حديثة التخرج، تنتظر استكمال إجراءات التوثيق.",
            years_experience=3,
            rating=None,
            phone="+201234567892",
            email="dr.mona.elsherif@example.com",
            license_number="EG-DERM-55231",
            medical_degree="MBBCh",
            university="جامعة عين شمس",
            city="Cairo",
            # Submitted, waiting for an admin: the Sprint 12 review queue is
            # never empty in a fresh dev environment.
            verification_status=VerificationStatus.PENDING,
            submitted_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
        session.add_all([dr_amira, dr_khaled, dr_mona])
        await session.flush()

        # Two sample documents for her application, written to UPLOAD_DIR
        # like real uploads (tiny placeholder PDFs, not real licences).
        for document_type, title in (
            (DocumentType.MEDICAL_LICENSE, "medical-licence.pdf"),
            (DocumentType.NATIONAL_ID, "national-id.pdf"),
        ):
            sample = f"%PDF-1.4\n% Sample {title} for local development only\n".encode()
            stored_path, content_type, size = save_upload(BytesIO(sample), folder=f"doctors/{dr_mona.id}")
            session.add(
                DoctorDocument(
                    doctor_id=dr_mona.id,
                    document_type=document_type,
                    original_filename=title,
                    stored_path=stored_path,
                    content_type=content_type,
                    size_bytes=size,
                    uploaded_by_user_id=user_mona.id,
                )
            )

        session.add_all(
            [
                DoctorCredential(
                    doctor_id=dr_amira.id,
                    credential_type="board_certification",
                    issuing_authority="Egyptian Ministry of Health",
                    credential_number="EG-DERM-10422",
                    issue_date=date(2013, 6, 1),
                    verified=True,
                ),
                DoctorCredential(
                    doctor_id=dr_khaled.id,
                    credential_type="license",
                    issuing_authority="Egyptian Medical Syndicate",
                    credential_number="EG-MED-88213",
                    issue_date=date(2017, 3, 15),
                    verified=True,
                ),
                DoctorCredential(
                    doctor_id=dr_mona.id,
                    credential_type="license",
                    issuing_authority="Egyptian Medical Syndicate",
                    credential_number="EG-MED-99981",
                    issue_date=date(2022, 9, 1),
                    verified=False,
                ),
            ]
        )

        # --- Clinic staff (doctor <-> clinic memberships) ---
        session.add_all(
            [
                ClinicStaff(
                    clinic_id=clinic_zamalek.id,
                    doctor_id=dr_amira.id,
                    role=ClinicStaffRole.DOCTOR,
                    consultation_fee=500,
                    full_name=dr_amira.full_name,
                    email=dr_amira.email,
                ),
                ClinicStaff(
                    clinic_id=clinic_maadi.id,
                    doctor_id=dr_amira.id,
                    role=ClinicStaffRole.DOCTOR,
                    consultation_fee=450,
                    full_name=dr_amira.full_name,
                    email=dr_amira.email,
                ),
                ClinicStaff(
                    clinic_id=clinic_sheikh_zayed.id,
                    doctor_id=dr_khaled.id,
                    role=ClinicStaffRole.DOCTOR,
                    consultation_fee=700,
                    full_name=dr_khaled.full_name,
                    email=dr_khaled.email,
                ),
                ClinicStaff(
                    clinic_id=clinic_maadi.id,
                    doctor_id=dr_mona.id,
                    role=ClinicStaffRole.DOCTOR,
                    consultation_fee=400,
                    full_name=dr_mona.full_name,
                    email=dr_mona.email,
                ),
                ClinicStaff(
                    clinic_id=clinic_zamalek.id,
                    doctor_id=None,
                    user_id=user_yasmin.id,
                    role=ClinicStaffRole.CLINIC_ADMIN,
                    full_name="ياسمين عادل",
                    email="yasmin.adel@newlook-zamalek.example.com",
                ),
            ]
        )

        # --- Procedures ---
        botox = Procedure(
            name="Botox",
            slug="botox",
            category="injectable",
            description="حقن البوتوكس لتقليل التجاعيد التعبيرية.",
            typical_price_min=2500,
            typical_price_max=6000,
        )
        filler = Procedure(
            name="Dermal Filler",
            slug="dermal-filler",
            category="injectable",
            description="حقن الفيلر لملء التجاعيد وتحديد ملامح الوجه.",
            typical_price_min=3000,
            typical_price_max=8000,
        )
        laser_hair_removal = Procedure(
            name="Laser Hair Removal",
            slug="laser-hair-removal",
            category="laser",
            description="إزالة الشعر بالليزر.",
            typical_price_min=500,
            typical_price_max=2500,
        )
        chemical_peel = Procedure(
            name="Chemical Peel",
            slug="chemical-peel",
            category="skin_treatment",
            description="تقشير كيميائي لتحسين ملمس ولون البشرة.",
            typical_price_min=800,
            typical_price_max=2200,
        )
        session.add_all([botox, filler, laser_hair_removal, chemical_peel])
        await session.flush()

        session.add_all(
            [
                DoctorProcedure(
                    doctor_id=dr_amira.id, procedure_id=botox.id, clinic_id=clinic_zamalek.id,
                    price=4500, currency="EGP",
                ),
                DoctorProcedure(
                    doctor_id=dr_amira.id, procedure_id=chemical_peel.id, clinic_id=clinic_maadi.id,
                    price=1200, currency="EGP",
                ),
                DoctorProcedure(
                    doctor_id=dr_khaled.id, procedure_id=botox.id, clinic_id=clinic_sheikh_zayed.id,
                    price=3800, currency="EGP",
                ),
                DoctorProcedure(
                    doctor_id=dr_khaled.id, procedure_id=filler.id, clinic_id=clinic_sheikh_zayed.id,
                    price=5500, currency="EGP",
                ),
                DoctorProcedure(
                    doctor_id=dr_mona.id, procedure_id=laser_hair_removal.id, clinic_id=clinic_maadi.id,
                    price=900, currency="EGP",
                ),
            ]
        )

        # --- Availability (next few days, some booked) ---
        slots = []
        for doctor, clinic in [
            (dr_amira, clinic_zamalek),
            (dr_khaled, clinic_sheikh_zayed),
            (dr_mona, clinic_maadi),
        ]:
            for day_offset in range(1, 4):
                for hour in (10, 12, 15):
                    start = (NOW + timedelta(days=day_offset)).replace(
                        hour=hour, minute=0, second=0, microsecond=0
                    )
                    slots.append(
                        Availability(
                            doctor_id=doctor.id,
                            clinic_id=clinic.id,
                            start_time=start,
                            end_time=start + timedelta(minutes=30),
                            is_booked=False,
                        )
                    )
        session.add_all(slots)
        await session.flush()

        # --- Patients ---
        patient_nour = Patient(
            user_id=user_nour.id,
            full_name="نور محمد سيد",
            phone="+201555001122",
            email="nour.mohamed@example.com",
            date_of_birth=date(1994, 4, 12),
            gender="female",
            preferred_language=Language.AR,
        )
        patient_omar = Patient(
            user_id=user_omar.id,
            full_name="عمر عبد الرحمن",
            phone="+201555003344",
            email="omar.abdelrahman@example.com",
            date_of_birth=date(1988, 11, 2),
            gender="male",
            preferred_language=Language.AR,
        )
        session.add_all([patient_nour, patient_omar])
        await session.flush()

        session.add_all(
            [
                PatientConsent(
                    patient_id=patient_nour.id,
                    consent_type=ConsentType.DATA_PROCESSING,
                    granted=True,
                    consent_text_version="1.0",
                    granted_at=NOW - timedelta(days=2),
                ),
                PatientConsent(
                    patient_id=patient_nour.id,
                    consent_type=ConsentType.MEDICAL_ADVICE_DISCLAIMER,
                    granted=True,
                    consent_text_version="1.0",
                    granted_at=NOW - timedelta(days=2),
                ),
                PatientConsent(
                    patient_id=patient_omar.id,
                    consent_type=ConsentType.DATA_PROCESSING,
                    granted=True,
                    consent_text_version="1.0",
                    granted_at=NOW - timedelta(days=5),
                ),
            ]
        )

        # --- Conversation + messages + intake for patient_nour ---
        conversation = Conversation(
            patient_id=patient_nour.id,
            channel=ConversationChannel.WEB,
            language=Language.AR,
            status=ConversationStatus.ACTIVE,
        )
        session.add(conversation)
        await session.flush()

        session.add_all(
            [
                Message(
                    conversation_id=conversation.id,
                    role=MessageRole.USER,
                    content="عايزة حاجة تقلل الخطوط حوالين عيني",
                ),
                Message(
                    conversation_id=conversation.id,
                    role=MessageRole.ASSISTANT,
                    content="تمام، هساعدك في الموضوع ده. تحبي تحددي أكتر ايه الهدف من العلاج؟",
                    extra_data={"intent": "intake_followup"},
                ),
            ]
        )

        session.add(
            Intake(
                conversation_id=conversation.id,
                patient_id=patient_nour.id,
                concern="wrinkles",
                body_area="periorbital_area",
                goal="reduce_wrinkles",
                structured_data={
                    "concern": "wrinkles",
                    "body_area": "periorbital_area",
                    "goal": "reduce_wrinkles",
                },
                missing_fields=["severity", "duration"],
                status=IntakeStatus.IN_PROGRESS,
            )
        )

        # --- A second conversation that got escalated, with a safety event ---
        risky_conversation = Conversation(
            patient_id=patient_omar.id,
            channel=ConversationChannel.WHATSAPP,
            language=Language.AR,
            status=ConversationStatus.ESCALATED,
        )
        session.add(risky_conversation)
        await session.flush()

        session.add(
            Message(
                conversation_id=risky_conversation.id,
                role=MessageRole.USER,
                content="حصلي تورم شديد ومفاجئ في وشي بعد الفيلر من يومين وفيه صعوبة في التنفس",
            )
        )
        session.add(
            SafetyEvent(
                conversation_id=risky_conversation.id,
                patient_id=patient_omar.id,
                risk_level=RiskLevel.HIGH,
                red_flags=["sudden_facial_swelling", "difficulty_breathing", "post_procedure"],
                requires_human=True,
                resolved=False,
                notes="Possible allergic/vascular complication post-filler — escalated for immediate clinician review.",
            )
        )

        # --- An appointment booked on one of the generated slots ---
        first_slot = slots[0]
        first_slot.is_booked = True
        session.add(
            Appointment(
                patient_id=patient_nour.id,
                doctor_id=first_slot.doctor_id,
                clinic_id=first_slot.clinic_id,
                procedure_id=botox.id,
                availability_id=first_slot.id,
                status=AppointmentStatus.CONFIRMED,
                scheduled_start=first_slot.start_time,
                scheduled_end=first_slot.end_time,
                # Default clinic policy: changes allowed until 24h before.
                cancellable_until=first_slot.start_time - timedelta(hours=24),
                idempotency_key=str(uuid.uuid4()),
                notes="First-time patient, referred by intake chat.",
            )
        )

        await session.commit()

        # --- Knowledge library (data/knowledge/*.md), embedded and approved for local use ---
        report = await ingest_directory(session, default_knowledge_dir(), get_embedder(), approve_as=DEV_REVIEWER)
        logger.info("seed.knowledge", **{k: len(v) for k, v in report.items()})
        logger.info("seed.completed")

    print(f"\nSeeded dev logins (password for all: {DEV_PASSWORD}):")
    for role, identifier in DEV_ACCOUNTS:
        print(f"  {role:<15} {identifier}")


if __name__ == "__main__":
    asyncio.run(seed())
