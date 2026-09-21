import { useQuery } from "@tanstack/react-query";
import { fetchProcedures, type ProcedureListParams } from "@/services/procedure-service";

export function useProcedures(params: ProcedureListParams = {}) {
  return useQuery({
    queryKey: ["procedures", params],
    queryFn: () => fetchProcedures(params),
  });
}
