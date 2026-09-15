import { apiFetch, buildQuery } from "@/lib/api-client";
import type { Paginated } from "@/types/common";
import type { Appointment, AppointmentCreateInput } from "@/types/appointment";

export interface AppointmentListParams {
  page?: number;
  page_size?: number;
  patient_id?: string;
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
