export type AppointmentStatus = "pending" | "confirmed" | "cancelled" | "completed" | "no_show";

export interface Appointment {
  id: string;
  patient_id: string;
  doctor_id: string;
  clinic_id: string;
  procedure_id?: string | null;
  availability_id?: string | null;
  status: AppointmentStatus;
  scheduled_start: string;
  scheduled_end: string;
  idempotency_key?: string | null;
  notes?: string | null;
  /** Last moment the patient may cancel or reschedule online (clinic policy). */
  cancellable_until?: string | null;
  cancelled_at?: string | null;
  cancellation_reason?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AppointmentCreateInput {
  patient_id: string;
  doctor_id: string;
  clinic_id: string;
  procedure_id?: string | null;
  availability_id?: string | null;
  scheduled_start: string;
  scheduled_end: string;
  notes?: string | null;
  idempotency_key?: string;
}
