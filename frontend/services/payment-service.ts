import { apiFetch } from "@/lib/api-client";
import type { CheckoutResponse, Payment, PaymentMethod, PaymentQuote } from "@/types/payment";

export async function fetchPaymentQuote(availabilityId: string): Promise<PaymentQuote> {
  return apiFetch<PaymentQuote>(`/api/v1/payments/quote?availability_id=${encodeURIComponent(availabilityId)}`);
}

export interface CheckoutInput {
  availability_id: string;
  method: PaymentMethod;
  /** One key per attempt: a retried request can never start a second payment. */
  idempotency_key: string;
}

export async function startCheckout(input: CheckoutInput): Promise<CheckoutResponse> {
  return apiFetch<CheckoutResponse>("/api/v1/payments/checkout", { method: "POST", body: JSON.stringify(input) });
}

export async function fetchPayment(id: string): Promise<Payment> {
  return apiFetch<Payment>(`/api/v1/payments/${id}`);
}
