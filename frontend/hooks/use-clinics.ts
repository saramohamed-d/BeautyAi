import { useQuery } from "@tanstack/react-query";
import { fetchClinics, type ClinicListParams } from "@/services/clinic-service";

export function useClinics(params: ClinicListParams = {}) {
  return useQuery({
    queryKey: ["clinics", params],
    queryFn: () => fetchClinics(params),
  });
}
