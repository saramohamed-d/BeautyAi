"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { HOME, isPatientArea } from "@/lib/roles";

/**
 * Keeps doctors, clinic admins and platform admins on their own side of
 * the app: opening a patient screen (home, doctor search, booking, the
 * AI chat…) sends them to their dashboard instead. The API enforces the
 * real permissions; this only keeps each person's app uncluttered.
 */
export function RoleRedirect() {
  const { audience } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const staff = audience !== "guest" && audience !== "patient";

  useEffect(() => {
    if (staff && isPatientArea(pathname)) router.replace(HOME[audience]);
  }, [staff, audience, pathname, router]);

  return null;
}
