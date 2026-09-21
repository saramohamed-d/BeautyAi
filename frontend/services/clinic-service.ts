import { apiFetch, buildQuery } from "@/lib/api-client";
import type { Paginated } from "@/types/common";
import type { Clinic } from "@/types/clinic";
import type {
  ClinicHours,
  ClinicService,
  ClinicStaffMember,
  ClinicSummary,
  SlotGenerateResult,
} from "@/types/clinic";

export interface ClinicListParams {
  page?: number;
  page_size?: number;
  city?: string;
}

export async function fetchClinics(params: ClinicListParams = {}): Promise<Paginated<Clinic>> {
  return apiFetch<Paginated<Clinic>>(`/api/v1/clinics${buildQuery(params)}`);
}

export async function fetchClinic(id: string): Promise<Clinic> {
  return apiFetch<Clinic>(`/api/v1/clinics/${id}`);
}

// --- Clinic admin dashboard (Sprint 13) --------------------------------------

export function fetchClinicSummary(clinicId: string): Promise<ClinicSummary> {
  return apiFetch<ClinicSummary>(`/api/v1/clinics/${clinicId}/summary`);
}

export function fetchClinicStaff(clinicId: string): Promise<ClinicStaffMember[]> {
  return apiFetch<ClinicStaffMember[]>(`/api/v1/clinics/${clinicId}/staff`);
}

export interface StaffInput {
  role?: "doctor" | "clinic_admin";
  doctor_id?: string;
  full_name?: string;
  email?: string;
  phone?: string;
  consultation_fee?: number | null;
}

export function addClinicStaff(clinicId: string, input: StaffInput): Promise<ClinicStaffMember> {
  return apiFetch<ClinicStaffMember>(`/api/v1/clinics/${clinicId}/staff`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateClinicStaff(
  clinicId: string,
  staffId: string,
  input: StaffInput & { is_active?: boolean }
): Promise<ClinicStaffMember> {
  return apiFetch<ClinicStaffMember>(`/api/v1/clinics/${clinicId}/staff/${staffId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function removeClinicStaff(clinicId: string, staffId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/clinics/${clinicId}/staff/${staffId}`, { method: "DELETE" });
}

export function fetchClinicHours(clinicId: string): Promise<ClinicHours[]> {
  return apiFetch<ClinicHours[]>(`/api/v1/clinics/${clinicId}/hours`);
}

export function saveClinicHours(clinicId: string, days: ClinicHours[]): Promise<ClinicHours[]> {
  return apiFetch<ClinicHours[]>(`/api/v1/clinics/${clinicId}/hours`, {
    method: "PUT",
    body: JSON.stringify({ days }),
  });
}

export function fetchClinicServices(clinicId: string): Promise<ClinicService[]> {
  return apiFetch<ClinicService[]>(`/api/v1/clinics/${clinicId}/services`);
}

export function addClinicService(
  clinicId: string,
  input: { doctor_id: string; procedure_id: string; price: number }
): Promise<ClinicService> {
  return apiFetch<ClinicService>(`/api/v1/clinics/${clinicId}/services`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateClinicService(clinicId: string, serviceId: string, price: number): Promise<ClinicService> {
  return apiFetch<ClinicService>(`/api/v1/clinics/${clinicId}/services/${serviceId}`, {
    method: "PATCH",
    body: JSON.stringify({ price }),
  });
}

export function removeClinicService(clinicId: string, serviceId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/clinics/${clinicId}/services/${serviceId}`, { method: "DELETE" });
}

export function generateSlots(
  clinicId: string,
  input: { doctor_id: string; date_from: string; date_to: string; slot_minutes?: number }
): Promise<SlotGenerateResult> {
  return apiFetch<SlotGenerateResult>(`/api/v1/clinics/${clinicId}/slots/generate`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function deleteSlot(clinicId: string, availabilityId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/clinics/${clinicId}/slots/${availabilityId}`, { method: "DELETE" });
}

export function updateClinic(clinicId: string, patch: Record<string, unknown>): Promise<Clinic> {
  return apiFetch<Clinic>(`/api/v1/clinics/${clinicId}`, { method: "PATCH", body: JSON.stringify(patch) });
}
