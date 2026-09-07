"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

/**
 * App-wide client providers.
 *
 * Design decision: TanStack Query's QueryClient is created inside a
 * `useState` initializer, not as a module-level singleton.
 *
 * Why: Next.js App Router renders on the server per-request. A
 * module-level QueryClient would be shared across different users'
 * requests on the server, leaking cached data between them. Creating it
 * inside component state means each render tree (and therefore each
 * request, and each browser tab on the client) gets its own instance.
 *
 * This is also where auth context, theme, and toast providers will be
 * added in later sprints — kept as one composition point so page
 * components don't need to know about the app's global providers.
 */
export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: 1,
          },
        },
      })
  );

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
