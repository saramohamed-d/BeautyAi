"""Sprint 11: payments — quote, checkout, webhook-confirmed bookings, refunds, Paymob signing."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.enums import PaymentMethod
from app.models.payment import Payment, PaymentEvent
from app.models.scheduling import Availability
from app.payments.gateways import (
    CheckoutRequest,
    Customer,
    DemoGateway,
    InvalidSignature,
    PaymobGateway,
    get_gateway,
    paymob_hmac,
)
from tests.factories import make_availability, make_clinic, make_clinic_admin, make_doctor, register_patient


def _at(hours: float) -> dict:
    start = datetime.now(timezone.utc) + timedelta(hours=hours)
    return {"start_time": start.isoformat(), "end_time": (start + timedelta(minutes=30)).isoformat()}


async def _world(admin_client: AsyncClient, fee: float | None = 500) -> dict:
    doctor = await make_doctor(admin_client)
    clinic = await make_clinic(admin_client, cancellation_cutoff_hours=24)
    slot = await make_availability(admin_client, doctor["id"], clinic["id"], **_at(72))
    if fee is not None:
        resp = await admin_client.put(
            f"/api/v1/clinics/{clinic['id']}/doctors/{doctor['id']}/fee", json={"consultation_fee": fee}
        )
        assert resp.status_code == 200, resp.text
    return {"doctor": doctor, "clinic": clinic, "slot": slot}


async def _checkout(client: AsyncClient, headers: dict, slot_id: str, method: str = "card", key: str | None = None):
    return await client.post(
        "/api/v1/payments/checkout",
        headers=headers,
        json={"availability_id": slot_id, "method": method, "idempotency_key": key or str(uuid.uuid4())},
    )


async def _demo_event(client: AsyncClient, payment_id: str, outcome: str, amount_cents: int | None = None, tx=None):
    """Sends a correctly signed demo webhook, as the fake gateway would."""
    async with AsyncSessionLocal() as db:
        payment = await db.get(Payment, uuid.UUID(payment_id))
    gateway = DemoGateway()
    cents = amount_cents if amount_cents is not None else int(Decimal(payment.amount) * 100)
    body = gateway.event_body(payment.provider_order_id, outcome, cents, tx or f"tx-{uuid.uuid4().hex[:8]}")
    return await client.post(
        f"/api/v1/payments/webhooks/demo?signature={gateway.sign(body)}",
        content=body,
        headers={"content-type": "application/json"},
    )


async def _payment(client: AsyncClient, headers: dict, payment_id: str) -> dict:
    resp = await client.get(f"/api/v1/payments/{payment_id}", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


# --- Quote & fee ------------------------------------------------------------------------


async def test_quote_offers_online_methods_only_when_a_fee_is_set(admin_client: AsyncClient, client: AsyncClient) -> None:
    patient = await register_patient(client)
    with_fee = await _world(admin_client, fee=650)
    quote = (await client.get(f"/api/v1/payments/quote?availability_id={with_fee['slot']['id']}", headers=patient["headers"])).json()
    assert Decimal(quote["amount"]) == Decimal("650")
    assert quote["currency"] == "EGP"
    assert quote["methods"] == ["card", "wallet", "pay_at_clinic"]

    without_fee = await _world(admin_client, fee=None)
    quote = (await client.get(f"/api/v1/payments/quote?availability_id={without_fee['slot']['id']}", headers=patient["headers"])).json()
    assert quote["amount"] is None
    assert quote["methods"] == ["pay_at_clinic"]


async def test_online_payment_refused_without_a_fee(admin_client: AsyncClient, client: AsyncClient) -> None:
    world = await _world(admin_client, fee=None)
    patient = await register_patient(client)
    resp = await _checkout(client, patient["headers"], world["slot"]["id"], "card")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "online_payment_unavailable"


async def test_only_admins_and_the_clinic_admin_set_fees(admin_client: AsyncClient, client: AsyncClient) -> None:
    world = await _world(admin_client)
    url = f"/api/v1/clinics/{world['clinic']['id']}/doctors/{world['doctor']['id']}/fee"
    patient = await register_patient(client)
    assert (await client.put(url, json={"consultation_fee": 1}, headers=patient["headers"])).status_code == 403
    other_admin = await make_clinic_admin((await make_clinic(admin_client))["id"])
    assert (await client.put(url, json={"consultation_fee": 1}, headers=other_admin)).status_code == 403
    own_admin = await make_clinic_admin(world["clinic"]["id"])
    resp = await client.put(url, json={"consultation_fee": 300}, headers=own_admin)
    assert resp.status_code == 200
    assert Decimal(resp.json()["consultation_fee"]) == Decimal("300")


# --- Pay at clinic ----------------------------------------------------------------------


async def test_pay_at_clinic_books_immediately(admin_client: AsyncClient, client: AsyncClient) -> None:
    world = await _world(admin_client)
    patient = await register_patient(client)
    resp = await _checkout(client, patient["headers"], world["slot"]["id"], "pay_at_clinic")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["checkout_url"] is None
    assert body["payment"]["status"] == "due_at_clinic"
    assert body["appointment"]["availability_id"] == world["slot"]["id"]
    assert body["payment"]["appointment_id"] == body["appointment"]["id"]


# --- Online checkout (demo gateway) -----------------------------------------------------


async def test_checkout_holds_the_slot_and_books_only_after_the_webhook(admin_client: AsyncClient, client: AsyncClient) -> None:
    world = await _world(admin_client)
    patient = await register_patient(client)
    resp = await _checkout(client, patient["headers"], world["slot"]["id"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    payment_id = body["payment"]["id"]
    assert body["payment"]["status"] == "pending"
    assert body["appointment"] is None
    assert body["checkout_url"].endswith(f"/api/v1/payments/demo/checkout/{payment_id}")

    # Held for this patient: nobody else can start paying for it.
    other = await register_patient(client)
    assert (await _checkout(client, other["headers"], world["slot"]["id"])).status_code == 409

    # No appointment yet.
    appointments = (await client.get("/api/v1/appointments", headers=patient["headers"])).json()
    assert appointments["total"] == 0

    assert (await _demo_event(client, payment_id, "paid")).status_code == 200
    paid = await _payment(client, patient["headers"], payment_id)
    assert paid["status"] == "paid"
    assert paid["paid_at"] is not None
    appointment = (await client.get(f"/api/v1/appointments/{paid['appointment_id']}", headers=patient["headers"])).json()
    assert appointment["availability_id"] == world["slot"]["id"]
    slot = (await admin_client.get(f"/api/v1/availability/{world['slot']['id']}")).json()
    assert slot["is_booked"] is True


async def test_checkout_is_idempotent(admin_client: AsyncClient, client: AsyncClient) -> None:
    world = await _world(admin_client)
    patient = await register_patient(client)
    key = str(uuid.uuid4())
    first = await _checkout(client, patient["headers"], world["slot"]["id"], key=key)
    retry = await _checkout(client, patient["headers"], world["slot"]["id"], key=key)
    assert first.json()["payment"]["id"] == retry.json()["payment"]["id"]
    other = await register_patient(client)
    assert (await _checkout(client, other["headers"], world["slot"]["id"], key=key)).status_code == 409


async def test_duplicate_webhooks_change_nothing(admin_client: AsyncClient, client: AsyncClient) -> None:
    world = await _world(admin_client)
    patient = await register_patient(client)
    payment_id = (await _checkout(client, patient["headers"], world["slot"]["id"])).json()["payment"]["id"]
    tx = f"tx-{uuid.uuid4().hex[:8]}"
    for _ in range(3):
        assert (await _demo_event(client, payment_id, "paid", tx=tx)).status_code == 200
    async with AsyncSessionLocal() as db:
        events = (await db.scalars(select(PaymentEvent).where(PaymentEvent.payment_id == uuid.UUID(payment_id)))).all()
    assert len(events) == 1
    assert (await client.get("/api/v1/appointments", headers=patient["headers"])).json()["total"] == 1


async def test_declined_payment_can_be_retried(admin_client: AsyncClient, client: AsyncClient) -> None:
    world = await _world(admin_client)
    patient = await register_patient(client)
    payment_id = (await _checkout(client, patient["headers"], world["slot"]["id"])).json()["payment"]["id"]
    await _demo_event(client, payment_id, "failed")
    failed = await _payment(client, patient["headers"], payment_id)
    assert failed["status"] == "failed"
    assert failed["appointment_id"] is None
    # Second attempt on the gateway's page succeeds.
    await _demo_event(client, payment_id, "paid")
    assert (await _payment(client, patient["headers"], payment_id))["status"] == "paid"


async def test_bad_signature_is_rejected(admin_client: AsyncClient, client: AsyncClient) -> None:
    world = await _world(admin_client)
    patient = await register_patient(client)
    payment_id = (await _checkout(client, patient["headers"], world["slot"]["id"])).json()["payment"]["id"]
    async with AsyncSessionLocal() as db:
        order_id = (await db.get(Payment, uuid.UUID(payment_id))).provider_order_id
    body = DemoGateway().event_body(order_id, "paid", 50000, "tx-forged")
    resp = await client.post("/api/v1/payments/webhooks/demo?signature=forged", content=body)
    assert resp.status_code == 401
    assert (await _payment(client, patient["headers"], payment_id))["status"] == "pending"
    # Wrong provider name in the URL.
    assert (await client.post("/api/v1/payments/webhooks/paymob", content=body)).status_code == 404


async def test_amount_mismatch_is_refunded(admin_client: AsyncClient, client: AsyncClient) -> None:
    world = await _world(admin_client, fee=500)
    patient = await register_patient(client)
    payment_id = (await _checkout(client, patient["headers"], world["slot"]["id"])).json()["payment"]["id"]
    await _demo_event(client, payment_id, "paid", amount_cents=100)
    payment = await _payment(client, patient["headers"], payment_id)
    assert payment["status"] == "refunded"
    assert payment["appointment_id"] is None
    slot = (await admin_client.get(f"/api/v1/availability/{world['slot']['id']}")).json()
    assert slot["is_booked"] is False


async def test_late_payment_for_a_slot_someone_else_booked_is_refunded(admin_client: AsyncClient, client: AsyncClient) -> None:
    world = await _world(admin_client)
    patient = await register_patient(client)
    payment_id = (await _checkout(client, patient["headers"], world["slot"]["id"])).json()["payment"]["id"]
    # The payment window passes and another patient books the slot at the clinic desk.
    async with AsyncSessionLocal() as db:
        slot = await db.scalar(select(Availability).where(Availability.id == uuid.UUID(world["slot"]["id"])))
        slot.held_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        await db.commit()
    other = await register_patient(client)
    assert (await _checkout(client, other["headers"], world["slot"]["id"], "pay_at_clinic")).status_code == 200

    await _demo_event(client, payment_id, "paid")
    payment = await _payment(client, patient["headers"], payment_id)
    assert payment["status"] == "refunded"
    assert payment["failure_reason"] == "The time was no longer available"
    assert (await client.get("/api/v1/appointments", headers=patient["headers"])).json()["total"] == 0


async def test_failed_refund_is_flagged_for_an_admin(admin_client: AsyncClient, client: AsyncClient) -> None:
    class NoRefunds(DemoGateway):
        async def refund(self, transaction_id: str, amount: Decimal) -> bool:
            return False

    app.dependency_overrides[get_gateway] = NoRefunds
    try:
        world = await _world(admin_client)
        patient = await register_patient(client)
        payment_id = (await _checkout(client, patient["headers"], world["slot"]["id"])).json()["payment"]["id"]
        await _demo_event(client, payment_id, "paid", amount_cents=1)
        assert (await _payment(client, patient["headers"], payment_id))["status"] == "needs_refund"
        listed = (await admin_client.get("/api/v1/payments?status=needs_refund")).json()
        assert payment_id in {p["id"] for p in listed["items"]}
    finally:
        app.dependency_overrides.pop(get_gateway, None)


async def test_cancelling_a_paid_appointment_refunds_it(admin_client: AsyncClient, client: AsyncClient) -> None:
    world = await _world(admin_client)
    patient = await register_patient(client)
    payment_id = (await _checkout(client, patient["headers"], world["slot"]["id"])).json()["payment"]["id"]
    await _demo_event(client, payment_id, "paid")
    appointment_id = (await _payment(client, patient["headers"], payment_id))["appointment_id"]

    resp = await client.patch(
        f"/api/v1/appointments/{appointment_id}", json={"status": "cancelled"}, headers=patient["headers"]
    )
    assert resp.status_code == 200, resp.text
    payment = await _payment(client, patient["headers"], payment_id)
    assert payment["status"] == "refunded"
    assert payment["refunded_at"] is not None


# --- Permissions ------------------------------------------------------------------------


async def test_payments_are_private(admin_client: AsyncClient, client: AsyncClient) -> None:
    world = await _world(admin_client)
    owner = await register_patient(client)
    payment_id = (await _checkout(client, owner["headers"], world["slot"]["id"])).json()["payment"]["id"]
    stranger = await register_patient(client)
    assert (await client.get(f"/api/v1/payments/{payment_id}", headers=stranger["headers"])).status_code == 404
    assert (await client.get("/api/v1/payments", headers=stranger["headers"])).json()["total"] == 0
    assert (await client.get("/api/v1/payments", headers=owner["headers"])).json()["total"] == 1
    assert (await admin_client.get(f"/api/v1/payments/{payment_id}")).status_code == 200
    # Checkout is for patients.
    assert (await _checkout(admin_client, {}, world["slot"]["id"])).status_code == 403
    assert (await client.get(f"/api/v1/payments/{payment_id}")).status_code == 401


# --- Demo checkout page -----------------------------------------------------------------


async def test_demo_checkout_page_completes_through_the_webhook_code(admin_client: AsyncClient, client: AsyncClient) -> None:
    world = await _world(admin_client)
    patient = await register_patient(client)
    payment_id = (await _checkout(client, patient["headers"], world["slot"]["id"])).json()["payment"]["id"]
    page = await client.get(f"/api/v1/payments/demo/checkout/{payment_id}")
    assert page.status_code == 200
    assert "DEMO GATEWAY" in page.text

    done = await client.post(
        f"/api/v1/payments/demo/checkout/{payment_id}/complete",
        content="outcome=paid",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert done.status_code == 303
    assert done.headers["location"].endswith(f"/payment/return?payment_id={payment_id}")
    assert (await _payment(client, patient["headers"], payment_id))["status"] == "paid"


async def test_demo_pages_do_not_exist_with_a_real_gateway(client: AsyncClient) -> None:
    app.dependency_overrides[get_gateway] = lambda: PaymobGateway()
    try:
        assert (await client.get(f"/api/v1/payments/demo/checkout/{uuid.uuid4()}")).status_code == 404
    finally:
        app.dependency_overrides.pop(get_gateway, None)


# --- Paymob -----------------------------------------------------------------------------


def _paymob(transport: httpx.MockTransport | None = None) -> PaymobGateway:
    gateway = PaymobGateway(transport=transport)
    gateway.settings = get_settings().model_copy(
        update={
            "paymob_secret_key": "sk_test", "paymob_public_key": "pk_test", "paymob_hmac_secret": "hmac_test",
            "paymob_card_integration_id": 111, "paymob_wallet_integration_id": None,
        }
    )
    return gateway


def _callback(**overrides) -> dict:
    obj = {
        "id": 9001, "pending": False, "amount_cents": 50000, "success": True, "is_auth": False, "is_capture": False,
        "is_standalone_payment": True, "is_voided": False, "is_refunded": False, "is_3d_secure": True,
        "integration_id": 111, "has_parent_transaction": False, "created_at": "2026-09-19T12:00:00.000000",
        "currency": "EGP", "error_occured": False, "owner": 42,
        "order": {"id": 777}, "source_data": {"pan": "2346", "type": "card", "sub_type": "MasterCard"},
    }
    obj.update(overrides)
    return {"type": "TRANSACTION", "obj": obj}


def test_paymob_hmac_is_verified() -> None:
    gateway = _paymob()
    payload = _callback()
    body = json.dumps(payload).encode()
    signature = paymob_hmac(payload["obj"], "hmac_test")
    event = gateway.parse_webhook(body, {"hmac": signature})
    assert (event.provider_order_id, event.transaction_id, event.outcome, event.amount_cents) == ("777", "9001", "paid", 50000)

    with pytest.raises(InvalidSignature):
        gateway.parse_webhook(body, {"hmac": "0" * 128})
    tampered = _callback(amount_cents=1)
    with pytest.raises(InvalidSignature):
        gateway.parse_webhook(json.dumps(tampered).encode(), {"hmac": signature})
    with pytest.raises(InvalidSignature):
        gateway.parse_webhook(b"not json", {"hmac": signature})


def test_paymob_outcomes() -> None:
    gateway = _paymob()
    for overrides, expected in [
        ({"success": False}, "failed"),
        ({"success": False, "pending": True}, "pending"),
        ({"is_refunded": True}, "refunded"),
    ]:
        payload = _callback(**overrides)
        event = gateway.parse_webhook(json.dumps(payload).encode(), {"hmac": paymob_hmac(payload["obj"], "hmac_test")})
        assert event.outcome == expected, overrides


def test_paymob_hmac_uses_the_documented_field_order() -> None:
    # Concatenation of the documented fields in order; booleans lower-case.
    obj = _callback()["obj"]
    message = (
        "50000" "2026-09-19T12:00:00.000000" "EGP" "false" "false" "9001" "111" "true" "false" "false" "false" "true"
        "false" "777" "42" "false" "2346" "MasterCard" "card" "true"
    )
    import hashlib
    import hmac as hmac_lib

    assert paymob_hmac(obj, "k") == hmac_lib.new(b"k", message.encode(), hashlib.sha512).hexdigest()


async def test_paymob_intention_request() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["auth"], seen["body"] = str(request.url), request.headers["authorization"], json.loads(request.content)
        return httpx.Response(201, json={"client_secret": "cs_abc", "intention_order_id": 777})

    gateway = _paymob(httpx.MockTransport(handler))
    session = await gateway.create_checkout(
        CheckoutRequest(
            payment_id="pay-1", amount=Decimal("500.00"), currency="EGP", method=PaymentMethod.CARD,
            description="Beauty AI consultation", customer=Customer(first_name="Sara", last_name="Ali", email="s@example.com", phone="+201000000000"),
            return_url="http://front/payment/return?payment_id=pay-1", notification_url="http://api/webhooks/paymob",
            expires_in_seconds=900,
        )
    )
    assert seen["url"].endswith("/v1/intention/")
    assert seen["auth"] == "Token sk_test"
    body = seen["body"]
    assert (body["amount"], body["currency"], body["payment_methods"]) == (50000, "EGP", [111])
    assert body["special_reference"] == "pay-1"
    assert body["notification_url"] == "http://api/webhooks/paymob"
    assert body["billing_data"]["first_name"] == "Sara"
    assert session.provider_order_id == "777"
    assert session.checkout_url.endswith("/unifiedcheckout/?publicKey=pk_test&clientSecret=cs_abc")
    # Wallet isn't configured in this gateway, so it isn't offered.
    assert gateway.online_methods() == [PaymentMethod.CARD]


async def test_paymob_failure_becomes_a_502(admin_client: AsyncClient, client: AsyncClient) -> None:
    gateway = _paymob(httpx.MockTransport(lambda request: httpx.Response(500, json={"detail": "boom"})))
    app.dependency_overrides[get_gateway] = lambda: gateway
    try:
        world = await _world(admin_client)
        patient = await register_patient(client)
        resp = await _checkout(client, patient["headers"], world["slot"]["id"])
        assert resp.status_code == 502
        assert resp.json()["error"]["code"] == "payment_provider_error"
        payments = (await client.get("/api/v1/payments", headers=patient["headers"])).json()["items"]
        assert payments[0]["status"] == "failed"
    finally:
        app.dependency_overrides.pop(get_gateway, None)


async def test_payment_is_refunded_if_the_doctor_stops_being_bookable(
    client: AsyncClient, admin_client: AsyncClient
) -> None:
    """Verification withdrawn between checkout and payment: the money goes back."""
    world = await _world(admin_client)
    patient = await register_patient(client)
    payment_id = (await _checkout(client, patient["headers"], world["slot"]["id"])).json()["payment"]["id"]
    await admin_client.patch(f"/api/v1/doctors/{world['doctor']['id']}", json={"verification_status": "pending"})

    await _demo_event(client, payment_id, "paid")
    payment = await _payment(client, patient["headers"], payment_id)
    assert payment["status"] == "refunded"
    assert payment["appointment_id"] is None
