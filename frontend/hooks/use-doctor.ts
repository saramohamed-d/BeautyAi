import { useQuery } from "@tanstack/react-query";
import { fetchDoctor } from "@/services/doctor-service";

export function useDoctor(id: string | undefined) {
  return useQuery({
    queryKey: ["doctor", id],
    queryFn: () => fetchDoctor(id as string),
    enabled: Boolean(id),
  });
}
