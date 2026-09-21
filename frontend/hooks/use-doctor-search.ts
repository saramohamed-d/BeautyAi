import { useQuery } from "@tanstack/react-query";
import { searchDoctors, type DoctorSearchParams } from "@/services/doctor-service";

export function useDoctorSearch(params: DoctorSearchParams) {
  return useQuery({
    queryKey: ["doctor-search", params],
    queryFn: () => searchDoctors(params),
    placeholderData: (previous) => previous,
  });
}
