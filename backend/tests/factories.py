"""
Test data factories.

Design decision: these build prerequisite resources (a patient, a doctor,
a clinic...) THROUGH the real HTTP API (using the same AsyncClient a test
uses), not by inserting ORM rows directly. This means every test is also,
incidentally, continuously verifying that resource creation actually
works end-to-end — the same reason Sprint 1 chose to seed via the ORM
rather than raw SQL, applied one layer up.

The exception is login identities for doctors, clinic admins and
platform admins: there's no sign-up API for those roles yet (Sprints
12-14), so `create_user` inserts them directly. Patients sign up through
the real POST /auth/register (`register_patient`).
"""

import uuid

from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.db.session import AsyncSessionLocal
from app.models.clinic import ClinicStaff
from app.models.doctor import Doctor
from app.models.enums import ClinicStaffRole, UserRole, UserStatus
from app.models.user import User

TEST_PASSWORD = "correct-horse-42"
# bcrypt is deliberately slow; hash once for all directly-created test users.
_TEST_PASSWORD_HASH = hash_password(TEST_PASSWORD)


def unique_email() -> str:
    return f"user-{uuid.uuid4().hex[:12]}@example.com"


def unique_phone() -> str:
    return f"+2010{uuid.uuid4().int % 10**8:08d}"


def unique_slug(prefix: str = "proc") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def make_patient(client: AsyncClient, **overrides) -> dict:
    payload = {"full_name": "Test Patient", "phone": unique_phone()}
    payload.update(overrides)
    resp = await client.post("/api/v1/patients", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def make_doctor(client: AsyncClient, **overrides) -> dict:
    # Verified by default: most tests are about something else, and from
    # Sprint 12 an unverified doctor can't have slots or take bookings.
    payload = {"full_name": "Test Doctor", "specialty": "Dermatology", "verification_status": "verified"}
    payload.update(overrides)
    resp = await client.post("/api/v1/doctors", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def make_clinic(client: AsyncClient, **overrides) -> dict:
    payload = {"name": "Test Clinic", "city": "Cairo"}
    payload.update(overrides)
    resp = await client.post("/api/v1/clinics", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def make_procedure(client: AsyncClient, **overrides) -> dict:
    payload = {"name": "Test Procedure", "slug": unique_slug(), "category": "injectable"}
    payload.update(overrides)
    resp = await client.post("/api/v1/procedures", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def make_availability(client: AsyncClient, doctor_id: str, clinic_id: str, **overrides) -> dict:
    from datetime import datetime, timedelta, timezone

    start = datetime.now(timezone.utc) + timedelta(days=1)
    payload = {
        "doctor_id": doctor_id,
        "clinic_id": clinic_id,
        "start_time": start.isoformat(),
        "end_time": (start + timedelta(minutes=30)).isoformat(),
    }
    payload.update(overrides)
    resp = await client.post("/api/v1/availability", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def make_conversation(client: AsyncClient, **overrides) -> dict:
    payload = {"channel": "web", "language": "ar"}
    payload.update(overrides)
    resp = await client.post("/api/v1/conversations", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- Users & auth -----------------------------------------------------------


def bearer(user: User) -> dict[str, str]:
    token, _ = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


async def create_user(role: UserRole, status: UserStatus = UserStatus.ACTIVE, **overrides) -> User:
    async with AsyncSessionLocal() as db:
        user = User(
            email=overrides.pop("email", unique_email()),
            phone=overrides.pop("phone", None),
            password_hash=_TEST_PASSWORD_HASH,
            role=role,
            status=status,
            **overrides,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def register_patient(client: AsyncClient, **overrides) -> dict:
    """Signs a patient up via the API. Returns the session body plus ready-made `headers`."""
    payload = {
        "full_name": "Test Patient",
        "email": unique_email(),
        "phone": unique_phone(),
        "password": TEST_PASSWORD,
    }
    payload.update(overrides)
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    body["headers"] = {"Authorization": f"Bearer {body['access_token']}"}
    return body


async def make_doctor_user(admin_client: AsyncClient, **doctor_overrides) -> tuple[dict, dict[str, str]]:
    """A doctor profile with a linked doctor login. Returns (doctor json, auth headers)."""
    doctor = await make_doctor(admin_client, **doctor_overrides)
    user = await create_user(UserRole.DOCTOR)
    async with AsyncSessionLocal() as db:
        row = await db.get(Doctor, uuid.UUID(doctor["id"]))
        row.user_id = user.id
        await db.commit()
    return doctor, bearer(user)


async def make_clinic_admin(clinic_id: str) -> dict[str, str]:
    """A clinic-admin login managing `clinic_id`. Returns auth headers."""
    user = await create_user(UserRole.CLINIC_ADMIN)
    async with AsyncSessionLocal() as db:
        db.add(
            ClinicStaff(
                clinic_id=uuid.UUID(clinic_id),
                user_id=user.id,
                role=ClinicStaffRole.CLINIC_ADMIN,
                full_name="Clinic Admin",
                email=user.email,
            )
        )
        await db.commit()
    return bearer(user)
