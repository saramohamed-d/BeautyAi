import { useQuery } from "@tanstack/react-query";
import { fetchDoctors, type DoctorListParams } from "@/services/doctor-service";

export function useDoctors(params: DoctorListParams = {}) {
  return useQuery({
    queryKey: ["doctors", params],
    queryFn: () => fetchDoctors(params),
  });
}
