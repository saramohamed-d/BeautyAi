"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { I18nProvider } from "@/lib/i18n/provider";
import { AuthProvider } from "@/lib/auth-context";
import { BookingProvider } from "@/lib/booking-context";
import type { Locale } from "@/lib/i18n/config";

/**
 * App-wide client providers, composed in one place.
 *
 * QueryClient is created inside useState: a module-level singleton would
 * leak cached data across different users' server-rendered requests.
 */
export function Providers({ locale, children }: { locale: Locale; children: React.ReactNode }) {
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
      <I18nProvider initialLocale={locale}>
        <AuthProvider>
          <BookingProvider>{children}</BookingProvider>
        </AuthProvider>
      </I18nProvider>
    </QueryClientProvider>
  );
}
