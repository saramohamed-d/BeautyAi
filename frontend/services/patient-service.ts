import { apiFetch } from "@/lib/api-client";
import type { Patient } from "@/types/patient";

export interface PatientUpdateInput {
  full_name?: string;
  email?: string;
  city?: string;
  preferred_language?: "en" | "ar";
  notify_email?: boolean;
  notify_sms?: boolean;
  notify_whatsapp?: boolean;
}

export function updatePatient(patientId: string, patch: PatientUpdateInput): Promise<Patient> {
  return apiFetch<Patient>(`/api/v1/patients/${patientId}`, { method: "PATCH", body: JSON.stringify(patch) });
}
