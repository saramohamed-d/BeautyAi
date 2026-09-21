import { apiFetch } from "@/lib/api-client";
import type { HealthResponse } from "@/types/health";

/**
 * Service layer for the health check.
 *
 * Design decision: every backend resource gets a `*-service.ts` module
 * exporting plain async functions (no React, no hooks). Hooks (see
 * hooks/use-health.ts) wrap these functions with TanStack Query.
 *
 * Why the split: services are trivially unit-testable and reusable
 * outside React (e.g. in a script or server action) since they don't
 * depend on any React context.
 */
export async function fetchHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/api/v1/health");
}
