import { apiFetch, buildQuery } from "@/lib/api-client";
import type { Paginated } from "@/types/common";
import type { Appointment, AppointmentCreateInput } from "@/types/appointment";

export interface AppointmentListParams {
  page?: number;
  page_size?: number;
  patient_id?: string;
  /** Clinic admins and platform admins only; others are scoped by the API. */
  clinic_id?: string;
  doctor_id?: string;
  status?: string;
}

export async function fetchAppointments(params: AppointmentListParams = {}): Promise<Paginated<Appointment>> {
  return apiFetch<Paginated<Appointment>>(`/api/v1/appointments${buildQuery(params)}`);
}

export async function createAppointment(input: AppointmentCreateInput): Promise<Appointment> {
  return apiFetch<Appointment>("/api/v1/appointments", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function fetchAppointment(id: string): Promise<Appointment> {
  return apiFetch<Appointment>(`/api/v1/appointments/${id}`);
}

/** Staff status changes (confirm, complete, no-show). Patients only cancel or edit notes. */
export async function updateAppointment(id: string, patch: { status?: string; notes?: string }): Promise<Appointment> {
  return apiFetch<Appointment>(`/api/v1/appointments/${id}`, { method: "PATCH", body: JSON.stringify(patch) });
}

export async function cancelAppointment(id: string, reason?: string): Promise<Appointment> {
  return apiFetch<Appointment>(`/api/v1/appointments/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ status: "cancelled", ...(reason ? { cancellation_reason: reason } : {}) }),
  });
}

export async function rescheduleAppointment(id: string, availabilityId: string): Promise<Appointment> {
  return apiFetch<Appointment>(`/api/v1/appointments/${id}/reschedule`, {
    method: "POST",
    body: JSON.stringify({ availability_id: availabilityId }),
  });
}
