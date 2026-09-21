"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Page } from "@/components/layout/page";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth-context";
import { withNext } from "@/lib/safe-next";

/**
 * Old "Let Beauty AI book for me" page. Since Sprint 10 the booking agent
 * lives in the AI chat (backend: app/workflows/booking_agent.py), so this
 * only forwards old links there, with the request prefilled.
 */
function AssistantRedirect() {
  const router = useRouter();
  const specialty = useSearchParams().get("specialty") ?? "";
  const { status } = useAuth();

  useEffect(() => {
    if (status === "loading") return;
    const target = `/consultation?book=${encodeURIComponent(specialty)}`;
    router.replace(status === "authenticated" ? target : withNext("/login", target));
  }, [status, specialty, router]);

  return <Page width="narrow"><Skeleton className="h-64" /></Page>;
}

export default function AssistantPage() {
  return (
    <Suspense fallback={<Page width="narrow"><Skeleton className="h-64" /></Page>}>
      <AssistantRedirect />
    </Suspense>
  );
}
