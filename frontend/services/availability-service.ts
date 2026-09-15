import { apiFetch, buildQuery } from "@/lib/api-client";
import type { Paginated } from "@/types/common";
import type { Availability } from "@/types/availability";

export interface AvailabilityListParams {
  page?: number;
  page_size?: number;
  doctor_id?: string;
  clinic_id?: string;
  is_booked?: boolean;
  start_from?: string;
  start_to?: string;
}

export async function fetchAvailability(params: AvailabilityListParams = {}): Promise<Paginated<Availability>> {
  return apiFetch<Paginated<Availability>>(`/api/v1/availability${buildQuery(params)}`);
}
