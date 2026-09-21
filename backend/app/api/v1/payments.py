"""
Payments API (Sprint 11; docs/payments.md).

The webhook is public but only acts on correctly signed calls. The demo
checkout page exists only when PAYMENT_PROVIDER=demo (never in
staging/production, enforced in config).
"""

from html import escape
from uuid import UUID

from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentPrincipal, Principal, require_roles
from app.core.config import get_settings
from app.core.exceptions import NotFoundError, UnauthorizedError
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.enums import PaymentStatus, UserRole
from app.models.patient import Patient
from app.models.payment import Payment
from app.payments.gateways import DemoGateway, InvalidSignature, PaymentGateway, get_gateway, to_cents
from app.schemas.common import PaginatedResponse
from app.schemas.payment import CheckoutRequestBody, CheckoutResponse, PaymentQuote, PaymentRead
from app.services import availability_service, payment_service

router = APIRouter(prefix="/payments", tags=["payments"])
logger = get_logger(__name__)
PatientOnly = require_roles(UserRole.PATIENT)


def _read(payment: Payment) -> PaymentRead:
    data = PaymentRead.model_validate(payment)
    return data.model_copy(update={"status": payment_service.display_status(payment)})


async def _own_payment(db: AsyncSession, principal: Principal, payment_id: UUID) -> Payment:
    payment = await db.get(Payment, payment_id)
    if payment is None or not (principal.is_admin or payment.patient_id == principal.patient_id):
        raise NotFoundError(f"Payment '{payment_id}' not found")
    return payment


@router.get("/quote", response_model=PaymentQuote)
async def quote(
    availability_id: UUID,
    _: Principal = Depends(PatientOnly),
    db: AsyncSession = Depends(get_db),
    gateway: PaymentGateway = Depends(get_gateway),
) -> PaymentQuote:
    """The consultation fee for a slot and the payment methods available for it."""
    slot = await availability_service.get_availability(db, availability_id)
    fee, methods = await payment_service.available_methods(db, slot.doctor_id, slot.clinic_id, gateway)
    return PaymentQuote(
        availability_id=slot.id, amount=fee, methods=methods, hold_minutes=get_settings().payment_window_minutes
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    payload: CheckoutRequestBody,
    principal: Principal = Depends(PatientOnly),
    db: AsyncSession = Depends(get_db),
    gateway: PaymentGateway = Depends(get_gateway),
) -> CheckoutResponse:
    """
    Online (card / wallet): holds the slot for the payment window and returns
    the gateway's checkout URL; the appointment is created when the gateway
    confirms the payment. Pay at clinic: creates the appointment now.
    409 `slot_unavailable` or `online_payment_unavailable`; 502 if the gateway fails.
    """
    if principal.patient_id is None:
        raise NotFoundError("Patient profile not found")
    patient = await db.get(Patient, principal.patient_id)
    payment, appointment = await payment_service.start_checkout(
        db, patient=patient, availability_id=payload.availability_id, method=payload.method,
        idempotency_key=payload.idempotency_key, gateway=gateway,
    )
    return CheckoutResponse(
        payment=_read(payment),
        checkout_url=payment.checkout_url if payment.status == PaymentStatus.PENDING else None,
        appointment=appointment,
    )


@router.get("", response_model=PaginatedResponse[PaymentRead])
async def list_payments(
    principal: CurrentPrincipal,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: PaymentStatus | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[PaymentRead]:
    """Admins see all (e.g. ?status=needs_refund); patients see their own."""
    query = select(Payment)
    if not principal.is_admin:
        if principal.patient_id is None:
            return PaginatedResponse.build([], 0, page, page_size)
        query = query.where(Payment.patient_id == principal.patient_id)
    if status_filter is not None:
        query = query.where(Payment.status == status_filter)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = await db.scalars(query.order_by(Payment.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    return PaginatedResponse.build([_read(p) for p in rows.all()], total or 0, page, page_size)


@router.get("/{payment_id}", response_model=PaymentRead)
async def get_payment(payment_id: UUID, principal: CurrentPrincipal, db: AsyncSession = Depends(get_db)) -> PaymentRead:
    return _read(await _own_payment(db, principal, payment_id))


@router.post("/webhooks/{provider}")
async def webhook(
    provider: str, request: Request, db: AsyncSession = Depends(get_db), gateway: PaymentGateway = Depends(get_gateway)
) -> dict[str, bool]:
    """Gateway server-to-server notification. Acts only on a valid signature (401 otherwise)."""
    if provider != gateway.name:
        raise NotFoundError("Unknown payment provider")
    try:
        event = gateway.parse_webhook(await request.body(), dict(request.query_params))
    except InvalidSignature:
        logger.warning("payment.webhook_bad_signature", provider=provider)
        raise UnauthorizedError("Invalid signature") from None
    await payment_service.handle_event(db, event, gateway)
    return {"received": True}


# --- Demo checkout (PAYMENT_PROVIDER=demo only) ------------------------------------------


def _demo_gateway(gateway: PaymentGateway = Depends(get_gateway)) -> DemoGateway:
    if not isinstance(gateway, DemoGateway):
        raise NotFoundError("Not found")
    return gateway


@router.get("/demo/checkout/{payment_id}", response_class=HTMLResponse, include_in_schema=False)
async def demo_checkout_page(
    payment_id: UUID, db: AsyncSession = Depends(get_db), _: DemoGateway = Depends(_demo_gateway)
) -> HTMLResponse:
    payment = await db.get(Payment, payment_id)
    if payment is None:
        raise NotFoundError("Payment not found")
    doctor = await db.get(Doctor, payment.doctor_id)
    clinic = await db.get(Clinic, payment.clinic_id)
    action = f"/api/v1/payments/demo/checkout/{payment.id}/complete"
    return HTMLResponse(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Demo checkout</title>
<style>body{{font-family:system-ui,sans-serif;background:#f4f4f5;margin:0;padding:24px;color:#18181b}}
.box{{max-width:380px;margin:auto;background:#fff;border-radius:14px;padding:20px;border:1px solid #e4e4e7}}
.tag{{display:inline-block;background:#fef3c7;color:#92400e;border-radius:6px;padding:2px 8px;font-size:12px;font-weight:700}}
button{{width:100%;height:46px;border:0;border-radius:10px;font-weight:700;font-size:15px;margin-top:10px;cursor:pointer}}
.pay{{background:#16a34a;color:#fff}}.fail{{background:#e4e4e7;color:#18181b}}</style></head><body><div class="box">
<span class="tag">DEMO GATEWAY — no real money</span>
<h1 style="font-size:20px">Pay {escape(str(payment.amount))} {escape(payment.currency)}</h1>
<p>{escape(doctor.full_name if doctor else "")} · {escape(clinic.name if clinic else "")}<br>Method: {escape(payment.method.value)}</p>
<form method="post" action="{action}"><input type="hidden" name="outcome" value="paid"><button class="pay" id="pay">Pay successfully</button></form>
<form method="post" action="{action}"><input type="hidden" name="outcome" value="failed"><button class="fail" id="decline">Decline payment</button></form>
</div></body></html>""")


@router.post("/demo/checkout/{payment_id}/complete", include_in_schema=False)
async def demo_checkout_complete(
    payment_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    gateway: DemoGateway = Depends(_demo_gateway),
) -> RedirectResponse:
    """Simulates the gateway: sends a signed event through the normal webhook code, then returns the browser."""
    outcome = parse_qs((await request.body()).decode()).get("outcome", [""])[0]
    payment = await db.get(Payment, payment_id)
    if payment is None or payment.provider_order_id is None or outcome not in ("paid", "failed"):
        raise NotFoundError("Payment not found")
    body = gateway.event_body(
        payment.provider_order_id, outcome, to_cents(payment.amount or 0), transaction_id=f"demo-tx-{payment.id}-{outcome}"
    )
    event = gateway.parse_webhook(body, {"signature": gateway.sign(body)})
    await payment_service.handle_event(db, event, gateway)
    return RedirectResponse(f"{get_settings().frontend_url}/payment/return?payment_id={payment.id}", status_code=303)
