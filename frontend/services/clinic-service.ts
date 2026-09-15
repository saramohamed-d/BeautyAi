import { apiFetch, buildQuery } from "@/lib/api-client";
import type { Paginated } from "@/types/common";
import type { Clinic } from "@/types/clinic";

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
