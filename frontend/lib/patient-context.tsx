"use client";

import { createContext, useContext, useState, type ReactNode } from "react";
import type { Patient } from "@/types/patient";

/**
 * PatientContext — a PLACEHOLDER identity layer, not authentication.
 *
 * Sprint 3 explicitly excludes backend auth (no JWT, no sessions, no
 * passwords). What patients actually need in this sprint is just "which
 * Patient row am I" so /account and /appointments can show real data
 * from Sprint 2's API. This context holds that identity in memory only
 * (React state — no cookies, no localStorage, no backend session).
 *
 * It's set two ways, both calling the real Patient API, never inventing
 * a fake user:
 *   1. The login/signup UI forms below (which look up or create a real
 *      Patient row by phone number — see services/patient-service.ts).
 *   2. The booking flow's "your details" step, so a booking works even
 *      if the person skipped login entirely.
 *
 * KNOWN LIMITATION (documented, not hidden): reloading the page clears
 * this. There is no persistence and no real login. A real auth system
 * is out of scope for Sprint 3 per the brief.
 */

interface PatientContextValue {
  patient: Patient | null;
  setPatient: (patient: Patient | null) => void;
}

const PatientContext = createContext<PatientContextValue | undefined>(undefined);

export function PatientProvider({ children }: { children: ReactNode }) {
  const [patient, setPatient] = useState<Patient | null>(null);
  return <PatientContext.Provider value={{ patient, setPatient }}>{children}</PatientContext.Provider>;
}

export function usePatientContext(): PatientContextValue {
  const ctx = useContext(PatientContext);
  if (!ctx) throw new Error("usePatientContext must be used within PatientProvider");
  return ctx;
}
