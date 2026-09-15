import { useQuery } from "@tanstack/react-query";
import { fetchAvailability, type AvailabilityListParams } from "@/services/availability-service";

export function useAvailability(params: AvailabilityListParams, enabled = true) {
  return useQuery({
    queryKey: ["availability", params],
    queryFn: () => fetchAvailability(params),
    enabled: enabled && Boolean(params.doctor_id),
  });
}
