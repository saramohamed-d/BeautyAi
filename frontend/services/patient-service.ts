import { apiFetch, buildQuery } from "@/lib/api-client";
import type { Paginated } from "@/types/common";
import type { Patient, PatientCreateInput } from "@/types/patient";

export async function searchPatientsByPhone(phone: string): Promise<Paginated<Patient>> {
  return apiFetch<Paginated<Patient>>(`/api/v1/patients${buildQuery({ search: phone, page_size: 5 })}`);
}

export async function createPatient(input: PatientCreateInput): Promise<Patient> {
  return apiFetch<Patient>("/api/v1/patients", { method: "POST", body: JSON.stringify(input) });
}

/**
 * Finds an existing patient by exact phone match, or creates a new one.
 * This is the closest Sprint 3 gets to "login" — it's a real API-backed
 * identity lookup, not an invented auth system. See lib/patient-context.tsx.
 */
export async function findOrCreatePatient(input: PatientCreateInput): Promise<Patient> {
  const results = await searchPatientsByPhone(input.phone);
  const exactMatch = results.items.find((p) => p.phone === input.phone);
  if (exactMatch) return exactMatch;
  return createPatient(input);
}
