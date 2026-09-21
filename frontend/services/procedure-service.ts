import { apiFetch, buildQuery } from "@/lib/api-client";
import type { Paginated } from "@/types/common";
import type { Procedure } from "@/types/procedure";

export interface ProcedureListParams {
  page?: number;
  page_size?: number;
  category?: string;
}

export async function fetchProcedures(params: ProcedureListParams = {}): Promise<Paginated<Procedure>> {
  return apiFetch<Paginated<Procedure>>(`/api/v1/procedures${buildQuery(params)}`);
}

export async function fetchProcedure(id: string): Promise<Procedure> {
  return apiFetch<Procedure>(`/api/v1/procedures/${id}`);
}
