import { useQuery } from "@tanstack/react-query";
import { fetchProcedure } from "@/services/procedure-service";

export function useProcedure(id: string | undefined) {
  return useQuery({
    queryKey: ["procedure", id],
    queryFn: () => fetchProcedure(id as string),
    enabled: Boolean(id),
  });
}
