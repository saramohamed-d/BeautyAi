"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { PatientProvider } from "@/lib/patient-context";
import { BookingProvider } from "@/lib/booking-context";

/**
 * App-wide client providers, composed in one place so page components
 * don't need to know about the app's provider stack.
 *
 * QueryClient is created inside useState (Sprint 0 decision, preserved):
 * a module-level singleton would leak cached data across different
 * users' server-rendered requests.
 */
export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 30_000, retry: 1 },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <PatientProvider>
        <BookingProvider>{children}</BookingProvider>
      </PatientProvider>
    </QueryClientProvider>
  );
}
