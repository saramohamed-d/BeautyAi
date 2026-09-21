import type { Appointment } from "@/types/appointment";

export type PaymentMethod = "card" | "wallet" | "pay_at_clinic";

export type PaymentStatus =
  | "pending"
  | "paid"
  | "failed"
  | "expired"
  | "due_at_clinic"
  | "refund_pending"
  | "refunded"
  | "needs_refund";

export interface PaymentQuote {
  availability_id: string;
  /** Null when the clinic hasn't set a fee: only pay_at_clinic is offered. */
  amount: string | null;
  currency: string;
  methods: PaymentMethod[];
  hold_minutes: number;
}

export interface Payment {
  id: string;
  status: PaymentStatus;
  method: PaymentMethod;
  amount: string | null;
  currency: string;
  provider: string;
  availability_id: string | null;
  appointment_id: string | null;
  doctor_id: string;
  clinic_id: string;
  expires_at: string | null;
  paid_at: string | null;
  refunded_at: string | null;
  failure_reason: string | null;
  created_at: string;
}

export interface CheckoutResponse {
  payment: Payment;
  /** Online methods: where to send the patient to pay. */
  checkout_url: string | null;
  /** Pay at clinic: the appointment, booked immediately. */
  appointment: Appointment | null;
}
