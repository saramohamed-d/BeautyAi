import { apiFetch, buildQuery } from "@/lib/api-client";
import type { Paginated } from "@/types/common";
import type { Doctor } from "@/types/doctor";

export interface DoctorListParams {
  page?: number;
  page_size?: number;
  specialty?: string;
  is_active?: boolean;
}

export async function fetchDoctors(params: DoctorListParams = {}): Promise<Paginated<Doctor>> {
  return apiFetch<Paginated<Doctor>>(`/api/v1/doctors${buildQuery(params)}`);
}

export async function fetchDoctor(id: string): Promise<Doctor> {
  return apiFetch<Doctor>(`/api/v1/doctors/${id}`);
}
