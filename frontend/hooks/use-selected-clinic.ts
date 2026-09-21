"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import type { ClinicMembership } from "@/types/clinic";

const STORAGE_KEY = "beautyai.clinic";

/**
 * Which clinic the dashboard is showing.
 *
 * Most clinic admins manage exactly one clinic, so the first is selected
 * automatically. The choice is remembered per browser (a convenience, not
 * a permission: the backend checks membership on every request).
 */
export function useSelectedClinic(): {
  clinics: ClinicMembership[];
  clinic: ClinicMembership | null;
  selectClinic: (id: string) => void;
} {
  const { clinics } = useAuth();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    const first = clinics[0];
    if (!first) return;
    let stored: string | null = null;
    try {
      stored = window.localStorage.getItem(STORAGE_KEY);
    } catch {
      stored = null; // private mode or blocked storage: fall back to the first clinic
    }
    setSelectedId(clinics.some((clinic) => clinic.id === stored) ? stored : first.id);
  }, [clinics]);

  function selectClinic(id: string) {
    setSelectedId(id);
    try {
      window.localStorage.setItem(STORAGE_KEY, id);
    } catch {
      // Not remembering the choice is fine; the page still works.
    }
  }

  return {
    clinics,
    clinic: clinics.find((clinic) => clinic.id === selectedId) ?? null,
    selectClinic,
  };
}
