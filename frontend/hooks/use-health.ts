import { useQuery } from "@tanstack/react-query";
import { fetchHealth } from "@/services/health-service";

/**
 * React hook for the backend health status.
 *
 * Design decision: components call `useHealth()`, never `fetchHealth()`
 * or `apiFetch()` directly. TanStack Query gives us caching, automatic
 * retry, and loading/error states for free — the same pattern every
 * other data-fetching hook in the app (doctors, clinics, appointments)
 * will follow starting Sprint 11+.
 */
export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 15_000,
  });
}
