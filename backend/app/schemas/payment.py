from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PaymentMethod, PaymentStatus
from app.schemas.appointment import AppointmentRead


class PaymentQuote(BaseModel):
    availability_id: UUID
    # Null when the clinic hasn't set a fee: then only pay_at_clinic is offered.
    amount: Decimal | None
    currency: str = "EGP"
    methods: list[PaymentMethod]
    hold_minutes: int


class CheckoutRequestBody(BaseModel):
    availability_id: UUID
    method: PaymentMethod
    # One key per checkout attempt, so a retried request can't start two payments.
    idempotency_key: str = Field(..., min_length=8, max_length=128)


class PaymentRead(BaseModel):
    id: UUID
    status: PaymentStatus
    method: PaymentMethod
    amount: Decimal | None
    currency: str
    provider: str
    availability_id: UUID | None
    appointment_id: UUID | None
    doctor_id: UUID
    clinic_id: UUID
    expires_at: datetime | None
    paid_at: datetime | None
    refunded_at: datetime | None
    failure_reason: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CheckoutResponse(BaseModel):
    payment: PaymentRead
    # Online: send the patient here. Null for pay at clinic.
    checkout_url: str | None
    # Pay at clinic: the appointment, created immediately.
    appointment: AppointmentRead | None = None


class ConsultationFeeUpdate(BaseModel):
    consultation_fee: Decimal | None = Field(None, ge=0, le=100000, decimal_places=2)


class ConsultationFeeRead(BaseModel):
    clinic_id: UUID
    doctor_id: UUID
    consultation_fee: Decimal | None
