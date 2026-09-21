import { apiFetch, buildQuery } from "@/lib/api-client";
import type { Paginated } from "@/types/common";
import type { Availability, SlotHold } from "@/types/availability";

export interface AvailabilityListParams {
  page?: number;
  page_size?: number;
  doctor_id?: string;
  clinic_id?: string;
  is_booked?: boolean;
  start_from?: string;
  start_to?: string;
  /** Only slots bookable now: future, not booked, not held by someone else. */
  available?: boolean;
}

export async function fetchAvailability(params: AvailabilityListParams = {}): Promise<Paginated<Availability>> {
  return apiFetch<Paginated<Availability>>(`/api/v1/availability${buildQuery(params)}`);
}

/** Reserves a slot for the logged-in patient while they pay (the server decides how long). */
export async function holdSlot(availabilityId: string): Promise<SlotHold> {
  return apiFetch<SlotHold>(`/api/v1/availability/${availabilityId}/hold`, { method: "POST" });
}

export async function releaseHold(availabilityId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/availability/${availabilityId}/hold`, { method: "DELETE" });
}

export async function fetchSlot(availabilityId: string): Promise<Availability> {
  return apiFetch<Availability>(`/api/v1/availability/${availabilityId}`);
}
