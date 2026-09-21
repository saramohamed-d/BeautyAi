"""
Payment gateways.

The rest of the app talks to `PaymentGateway` only. Two implementations:

- PaymobGateway (Egypt): the Intention API and Unified Checkout, with the
  transaction-processed webhook verified by HMAC-SHA512. Built from
  Paymob's developer documentation (links in docs/payments.md); it has
  not been exercised against a live Paymob account yet.
- DemoGateway: a fake checkout page served by this API, for local
  development and tests. Its "webhook" is signed and parsed through the
  same interface, so the processing code is the same as with Paymob.

Only a verified webhook ever marks a payment as paid. The browser coming
back from checkout proves nothing.
"""

import hashlib
import hmac
import json
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from typing import Any, Literal, Protocol

import httpx

from app.core.config import get_settings
from app.core.exceptions import PaymentProviderError
from app.core.logging import get_logger
from app.models.enums import PaymentMethod

logger = get_logger(__name__)

Outcome = Literal["paid", "failed", "refunded", "pending"]


class InvalidSignature(Exception):
    pass


@dataclass(frozen=True)
class Customer:
    first_name: str
    last_name: str
    email: str
    phone: str


@dataclass(frozen=True)
class CheckoutRequest:
    payment_id: str
    amount: Decimal  # EGP
    currency: str
    method: PaymentMethod
    description: str
    customer: Customer
    return_url: str
    notification_url: str
    expires_in_seconds: int


@dataclass(frozen=True)
class CheckoutSession:
    provider_order_id: str
    checkout_url: str


@dataclass(frozen=True)
class GatewayEvent:
    provider_order_id: str
    transaction_id: str
    outcome: Outcome
    amount_cents: int
    payload: dict[str, Any]


class PaymentGateway(Protocol):
    name: str

    def online_methods(self) -> list[PaymentMethod]: ...

    async def create_checkout(self, request: CheckoutRequest) -> CheckoutSession: ...

    def parse_webhook(self, body: bytes, query: dict[str, str]) -> GatewayEvent: ...

    async def refund(self, transaction_id: str, amount: Decimal) -> bool: ...


def to_cents(amount: Decimal) -> int:
    return int((Decimal(amount) * 100).quantize(Decimal("1")))


def _outcome(success: bool, pending: bool, refunded: bool) -> Outcome:
    if refunded:
        return "refunded"
    if pending:
        return "pending"
    return "paid" if success else "failed"


# --- Paymob -------------------------------------------------------------------------

# Paymob's transaction-processed HMAC: SHA-512 over these values, concatenated
# in exactly this order, booleans as lowercase "true"/"false", with the HMAC
# secret; delivered as the `hmac` query parameter.
PAYMOB_HMAC_FIELDS = (
    "amount_cents", "created_at", "currency", "error_occured", "has_parent_transaction", "id",
    "integration_id", "is_3d_secure", "is_auth", "is_capture", "is_refunded", "is_standalone_payment",
    "is_voided", "order.id", "owner", "pending", "source_data.pan", "source_data.sub_type",
    "source_data.type", "success",
)


def _field(obj: dict[str, Any], dotted: str) -> str:
    value: Any = obj
    for part in dotted.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    if isinstance(value, bool):
        return "true" if value else "false"
    return "" if value is None else str(value)


def paymob_hmac(obj: dict[str, Any], secret: str) -> str:
    message = "".join(_field(obj, name) for name in PAYMOB_HMAC_FIELDS)
    return hmac.new(secret.encode(), message.encode(), hashlib.sha512).hexdigest()


class PaymobGateway:
    name = "paymob"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = get_settings()
        self._transport = transport  # tests inject a mock transport

    def _integration_id(self, method: PaymentMethod) -> int | None:
        return {
            PaymentMethod.CARD: self.settings.paymob_card_integration_id,
            PaymentMethod.WALLET: self.settings.paymob_wallet_integration_id,
        }.get(method)

    def online_methods(self) -> list[PaymentMethod]:
        return [m for m in (PaymentMethod.CARD, PaymentMethod.WALLET) if self._integration_id(m)]

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.settings.paymob_base_url,
            timeout=20,
            transport=self._transport,
            headers={"Authorization": f"Token {self.settings.paymob_secret_key}"},
        )

    async def create_checkout(self, request: CheckoutRequest) -> CheckoutSession:
        integration_id = self._integration_id(request.method)
        if integration_id is None:
            raise PaymentProviderError(f"Payment method '{request.method.value}' isn't configured")
        cents = to_cents(request.amount)
        c = request.customer
        body = {
            "amount": cents,
            "currency": request.currency,
            "payment_methods": [integration_id],
            "items": [{"name": request.description[:50], "amount": cents, "description": request.description, "quantity": 1}],
            # Paymob requires the full billing block; unused fields are "NA".
            "billing_data": {
                "first_name": c.first_name or "NA", "last_name": c.last_name or "NA", "email": c.email or "NA",
                "phone_number": c.phone or "NA", "apartment": "NA", "floor": "NA", "street": "NA", "building": "NA",
                "shipping_method": "NA", "postal_code": "NA", "city": "NA", "country": "EG", "state": "NA",
            },
            "special_reference": request.payment_id,
            "notification_url": request.notification_url,
            "redirection_url": request.return_url,
            "expiration": request.expires_in_seconds,
        }
        try:
            async with self._client() as client:
                response = await client.post("/v1/intention/", json=body)
        except httpx.HTTPError as exc:
            logger.warning("paymob.unreachable", error=type(exc).__name__)
            raise PaymentProviderError("The payment provider is unavailable. Please try again.") from exc
        if response.status_code >= 400:
            logger.warning("paymob.intention_rejected", status=response.status_code, body=response.text[:500])
            raise PaymentProviderError("The payment provider rejected the request.")
        data = response.json()
        checkout_url = (
            f"{self.settings.paymob_base_url}/unifiedcheckout/"
            f"?publicKey={self.settings.paymob_public_key}&clientSecret={data['client_secret']}"
        )
        return CheckoutSession(provider_order_id=str(data["intention_order_id"]), checkout_url=checkout_url)

    def parse_webhook(self, body: bytes, query: dict[str, str]) -> GatewayEvent:
        try:
            payload = json.loads(body)
            obj = payload["obj"]
        except (ValueError, KeyError, TypeError) as exc:
            raise InvalidSignature("Malformed callback") from exc
        expected = paymob_hmac(obj, self.settings.paymob_hmac_secret or "")
        if not hmac.compare_digest(expected, query.get("hmac", "")):
            raise InvalidSignature("HMAC mismatch")
        return GatewayEvent(
            provider_order_id=str((obj.get("order") or {}).get("id", "")),
            transaction_id=str(obj.get("id", "")),
            outcome=_outcome(bool(obj.get("success")), bool(obj.get("pending")), bool(obj.get("is_refunded"))),
            amount_cents=int(obj.get("amount_cents") or 0),
            payload=payload,
        )

    async def refund(self, transaction_id: str, amount: Decimal) -> bool:
        try:
            async with self._client() as client:
                response = await client.post(
                    "/api/acceptance/void_refund/refund",
                    json={"transaction_id": int(transaction_id), "amount_cents": to_cents(amount)},
                )
        except httpx.HTTPError:
            logger.warning("paymob.refund_unreachable", transaction_id=transaction_id)
            return False
        ok = response.status_code < 400 and bool(response.json().get("success", True))
        if not ok:
            logger.warning("paymob.refund_rejected", transaction_id=transaction_id, status=response.status_code)
        return ok


# --- Demo -------------------------------------------------------------------------------


class DemoGateway:
    """Fake checkout served at /api/v1/payments/demo/checkout/{id}. Local development and tests only."""

    name = "demo"

    def online_methods(self) -> list[PaymentMethod]:
        return [PaymentMethod.CARD, PaymentMethod.WALLET]

    @staticmethod
    def _secret() -> bytes:
        return hashlib.sha256(f"demo-payments:{get_settings().jwt_secret_key}".encode()).digest()

    def sign(self, body: bytes) -> str:
        return hmac.new(self._secret(), body, hashlib.sha256).hexdigest()

    async def create_checkout(self, request: CheckoutRequest) -> CheckoutSession:
        order_id = f"demo-{request.payment_id}"
        url = f"{get_settings().public_api_url}/api/v1/payments/demo/checkout/{request.payment_id}"
        return CheckoutSession(provider_order_id=order_id, checkout_url=url)

    def event_body(self, order_id: str, outcome: Outcome, amount_cents: int, transaction_id: str) -> bytes:
        return json.dumps(
            {"order_id": order_id, "outcome": outcome, "amount_cents": amount_cents, "transaction_id": transaction_id}
        ).encode()

    def parse_webhook(self, body: bytes, query: dict[str, str]) -> GatewayEvent:
        if not hmac.compare_digest(self.sign(body), query.get("signature", "")):
            raise InvalidSignature("Bad demo signature")
        data = json.loads(body)
        return GatewayEvent(
            provider_order_id=data["order_id"], transaction_id=data["transaction_id"], outcome=data["outcome"],
            amount_cents=data["amount_cents"], payload=data,
        )

    async def refund(self, transaction_id: str, amount: Decimal) -> bool:
        return True


@lru_cache
def get_gateway() -> PaymentGateway:
    """FastAPI dependency. Tests may override it."""
    return PaymobGateway() if get_settings().payment_provider == "paymob" else DemoGateway()
