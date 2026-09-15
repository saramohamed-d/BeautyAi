import { useQuery } from "@tanstack/react-query";
import { fetchClinic } from "@/services/clinic-service";

export function useClinic(id: string | undefined) {
  return useQuery({
    queryKey: ["clinic", id],
    queryFn: () => fetchClinic(id as string),
    enabled: Boolean(id),
  });
}
