"""Sprint 14: the platform admin dashboard — reports, users, manual refunds, audit log."""

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.enums import UserRole
from app.models.user import RefreshToken
from app.payments.gateways import DemoGateway, get_gateway
from tests.factories import (
    TEST_PASSWORD,
    bearer,
    create_user,
    make_availability,
    make_clinic,
    make_clinic_admin,
    make_doctor,
    register_patient,
)
from tests.test_doctor_verification import PDF, PNG, register_doctor, upload
from tests.test_payments import _demo_event


async def _paid_payment(client: AsyncClient, admin_client: AsyncClient) -> dict:
    """A patient who has paid online, so there is real money to refund."""
    doctor = await make_doctor(admin_client)
    clinic = await make_clinic(admin_client)
    await admin_client.put(
        f"/api/v1/clinics/{clinic['id']}/doctors/{doctor['id']}/fee", json={"consultation_fee": 500}
    )
    slot = await make_availability(admin_client, doctor["id"], clinic["id"])
    patient = await register_patient(client)
    checkout = await client.post(
        "/api/v1/payments/checkout",
        headers=patient["headers"],
        json={"availability_id": slot["id"], "method": "card", "idempotency_key": str(uuid.uuid4())},
    )
    payment_id = checkout.json()["payment"]["id"]
    await _demo_event(client, payment_id, "paid")
    return {"payment_id": payment_id, "patient": patient}


# --- Reports ------------------------------------------------------------------------------


async def test_overview_reports_the_platform(client: AsyncClient, admin_client: AsyncClient) -> None:
    doctor = await register_doctor(client)  # a pending application
    await upload(client, doctor, "medical_license")
    await upload(client, doctor, "national_id", name="id.png", content=PNG, content_type="image/png")
    await client.post(f"/api/v1/doctors/{doctor['doctor']['id']}/submit", headers=doctor["headers"])
    paid = await _paid_payment(client, admin_client)

    body = (await admin_client.get("/api/v1/admin/overview")).json()
    assert body["users"]["total"] > 0
    assert body["users"]["by_role"]["doctor"] >= 1
    assert body["doctors"]["awaiting_review"] >= 1
    assert body["attention"]["doctor_applications"] == body["doctors"]["awaiting_review"]
    assert Decimal(body["payments"]["paid_total"]) >= Decimal("500")
    assert body["clinics"]["total"] >= 1
    assert body["appointments"]["upcoming"] >= 1

    # Two weeks of days, oldest first, with today's booking counted.
    assert len(body["daily"]) == 14
    dates = [point["date"] for point in body["daily"]]
    assert dates == sorted(dates)
    assert sum(point["bookings"] for point in body["daily"]) >= 1
    assert sum(Decimal(point["revenue"]) for point in body["daily"]) >= Decimal("500")
    assert paid["payment_id"]


# --- Users ------------------------------------------------------------------------------


async def test_user_list_filters_and_shows_names(client: AsyncClient, admin_client: AsyncClient) -> None:
    patient = await register_patient(client, full_name="Mariam Saad")
    listed = (await admin_client.get(f"/api/v1/admin/users?q={patient['user']['email']}")).json()
    assert listed["total"] == 1
    assert listed["items"][0]["full_name"] == "Mariam Saad"
    assert listed["items"][0]["role"] == "patient"

    doctor = await register_doctor(client)
    by_role = (await admin_client.get("/api/v1/admin/users?role=doctor&page_size=100")).json()
    assert doctor["user"]["id"] in [item["id"] for item in by_role["items"]]
    assert {item["role"] for item in by_role["items"]} == {"doctor"}

    active_only = (await admin_client.get("/api/v1/admin/users?status=suspended&page_size=100")).json()
    assert all(item["status"] == "suspended" for item in active_only["items"])


async def test_suspending_a_user_ends_their_sessions(client: AsyncClient, admin_client: AsyncClient) -> None:
    patient = await register_patient(client)
    user_id = patient["user"]["id"]

    suspended = await admin_client.patch(
        f"/api/v1/admin/users/{user_id}", json={"status": "suspended", "reason": "Abusive messages"}
    )
    assert suspended.status_code == 200
    assert suspended.json()["status"] == "suspended"

    # Logging in again is refused...
    blocked = await client.post(
        "/api/v1/auth/login", json={"identifier": patient["user"]["email"], "password": TEST_PASSWORD}
    )
    assert blocked.status_code == 403
    # ...and the open session can't be renewed.
    async with AsyncSessionLocal() as db:
        tokens = (
            await db.scalars(select(RefreshToken).where(RefreshToken.user_id == uuid.UUID(user_id)))
        ).all()
    assert tokens and all(token.revoked_at is not None for token in tokens)

    restored = await admin_client.patch(f"/api/v1/admin/users/{user_id}", json={"status": "active"})
    assert restored.status_code == 200
    ok = await client.post(
        "/api/v1/auth/login", json={"identifier": patient["user"]["email"], "password": TEST_PASSWORD}
    )
    assert ok.status_code == 200


async def test_an_admin_cannot_suspend_themself(admin_client: AsyncClient) -> None:
    me = (await admin_client.get("/api/v1/auth/me")).json()
    refused = await admin_client.patch(f"/api/v1/admin/users/{me['user']['id']}", json={"status": "suspended"})
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "cannot_suspend_self"


async def test_unknown_user_is_404(admin_client: AsyncClient) -> None:
    assert (
        await admin_client.patch(f"/api/v1/admin/users/{uuid.uuid4()}", json={"status": "suspended"})
    ).status_code == 404


# --- Manual refunds -------------------------------------------------------------------------


async def test_admin_refunds_a_paid_payment(client: AsyncClient, admin_client: AsyncClient) -> None:
    paid = await _paid_payment(client, admin_client)
    refunded = await admin_client.post(
        f"/api/v1/admin/payments/{paid['payment_id']}/refund", json={"reason": "Clinic closed that day"}
    )
    assert refunded.status_code == 200, refunded.text
    assert refunded.json()["status"] == "refunded"
    assert refunded.json()["refunded_at"] is not None

    # A refunded payment can't be refunded again.
    again = await admin_client.post(
        f"/api/v1/admin/payments/{paid['payment_id']}/refund", json={"reason": "Duplicate"}
    )
    assert again.status_code == 409 and again.json()["error"]["code"] == "payment_not_refundable"


async def test_admin_clears_the_needs_refund_pile(client: AsyncClient, admin_client: AsyncClient) -> None:
    """The gateway refused the automatic refund; the admin retries it once it works."""

    class NoRefunds(DemoGateway):
        async def refund(self, transaction_id: str, amount: Decimal) -> bool:
            return False

    app.dependency_overrides[get_gateway] = NoRefunds
    try:
        paid = await _paid_payment(client, admin_client)
        stuck = await admin_client.post(
            f"/api/v1/admin/payments/{paid['payment_id']}/refund", json={"reason": "Patient asked"}
        )
        assert stuck.json()["status"] == "needs_refund"
        listed = (await admin_client.get("/api/v1/payments?status=needs_refund&page_size=100")).json()
        assert paid["payment_id"] in [item["id"] for item in listed["items"]]
    finally:
        app.dependency_overrides.pop(get_gateway, None)

    retried = await admin_client.post(
        f"/api/v1/admin/payments/{paid['payment_id']}/refund", json={"reason": "Retry after gateway fix"}
    )
    assert retried.status_code == 200
    assert retried.json()["status"] == "refunded"


async def test_a_pay_at_clinic_payment_cannot_be_refunded(client: AsyncClient, admin_client: AsyncClient) -> None:
    doctor = await make_doctor(admin_client)
    clinic = await make_clinic(admin_client)
    slot = await make_availability(admin_client, doctor["id"], clinic["id"])
    patient = await register_patient(client)
    checkout = await client.post(
        "/api/v1/payments/checkout",
        headers=patient["headers"],
        json={"availability_id": slot["id"], "method": "pay_at_clinic", "idempotency_key": str(uuid.uuid4())},
    )
    payment_id = checkout.json()["payment"]["id"]
    refused = await admin_client.post(
        f"/api/v1/admin/payments/{payment_id}/refund", json={"reason": "Nothing was taken"}
    )
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "payment_not_refundable"


# --- Audit log ------------------------------------------------------------------------------


async def test_admin_actions_are_written_to_the_audit_log(client: AsyncClient, admin_client: AsyncClient) -> None:
    patient = await register_patient(client)
    await admin_client.patch(
        f"/api/v1/admin/users/{patient['user']['id']}", json={"status": "suspended", "reason": "Spam"}
    )

    log = (await admin_client.get("/api/v1/admin/audit-events?action=user.&page_size=100")).json()
    entry = next(item for item in log["items"] if item["resource_id"] == patient["user"]["id"])
    assert entry["action"] == "user.suspended"
    assert entry["actor_type"] == "platform_admin"
    assert entry["extra_data"] == {"reason": "Spam"}

    # Filters: by resource and by what happened.
    by_resource = (
        await admin_client.get(f"/api/v1/admin/audit-events?resource_type=user&resource_id={patient['user']['id']}")
    ).json()
    assert [item["action"] for item in by_resource["items"]] == ["user.suspended"]
    assert (await admin_client.get("/api/v1/admin/audit-events?action=nothing.")).json()["total"] == 0


async def test_the_log_covers_verification_and_refunds(client: AsyncClient, admin_client: AsyncClient) -> None:
    doctor = await register_doctor(client)
    await upload(client, doctor, "medical_license", content=PDF)
    await upload(client, doctor, "national_id", name="id.png", content=PNG, content_type="image/png")
    await client.post(f"/api/v1/doctors/{doctor['doctor']['id']}/submit", headers=doctor["headers"])
    await admin_client.post(f"/api/v1/doctors/{doctor['doctor']['id']}/verification", json={"status": "verified"})
    paid = await _paid_payment(client, admin_client)
    await admin_client.post(f"/api/v1/admin/payments/{paid['payment_id']}/refund", json={"reason": "Goodwill"})

    doctor_log = (
        await admin_client.get(f"/api/v1/admin/audit-events?resource_id={doctor['doctor']['id']}")
    ).json()
    assert {item["action"] for item in doctor_log["items"]} == {
        "doctor.application_submitted",
        "doctor.verified",
    }
    payment_log = (
        await admin_client.get(f"/api/v1/admin/audit-events?resource_id={paid['payment_id']}")
    ).json()
    assert payment_log["items"][0]["action"] == "payment.refund_requested"
    assert payment_log["items"][0]["extra_data"]["outcome"] == "refunded"


# --- Permissions ------------------------------------------------------------------------------


async def test_only_platform_admins_get_in(client: AsyncClient, admin_client: AsyncClient) -> None:
    patient = await register_patient(client)
    doctor_user = await create_user(UserRole.DOCTOR)
    clinic = await make_clinic(admin_client)
    clinic_admin = await make_clinic_admin(clinic["id"])

    for headers in (patient["headers"], bearer(doctor_user), clinic_admin):
        for path in ("/api/v1/admin/overview", "/api/v1/admin/users", "/api/v1/admin/audit-events"):
            assert (await client.get(path, headers=headers)).status_code == 403, path
        assert (
            await client.patch(
                f"/api/v1/admin/users/{patient['user']['id']}", headers=headers, json={"status": "suspended"}
            )
        ).status_code == 403
    assert (await client.get("/api/v1/admin/overview")).status_code == 401


async def test_a_suspended_admin_loses_access(client: AsyncClient, admin_client: AsyncClient) -> None:
    """Suspension is checked on every request, not only at login."""
    other = await create_user(UserRole.PLATFORM_ADMIN)
    headers = bearer(other)
    assert (await client.get("/api/v1/admin/overview", headers=headers)).status_code == 200

    await admin_client.patch(f"/api/v1/admin/users/{other.id}", json={"status": "suspended"})
    # 401, not 403: a suspended account's token is simply not a valid one, and
    # the message doesn't tell the holder why (app/api/deps.py).
    assert (await client.get("/api/v1/admin/overview", headers=headers)).status_code == 401
