"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import type { Doctor } from "@/types/doctor";
import type { Clinic } from "@/types/clinic";
import type { Procedure } from "@/types/procedure";
import type { Availability } from "@/types/availability";

/**
 * BookingContext — carries the in-progress booking draft between
 * /booking, the AI chat's booking options and /payment.
 *
 * Design decision: plain React state in a provider mounted once in the
 * root layout, not localStorage/sessionStorage. Next.js App Router
 * client-side navigation (<Link>, router.push) keeps this provider
 * mounted across route changes, so the draft survives the /booking ->
 * /payment hop without needing browser storage or query-string
 * round-tripping of a large object.
 *
 * KNOWN LIMITATION: a hard page reload clears the draft. That's
 * acceptable for a prototype booking flow and is simpler than adding
 * persistence for a value that should only ever live a few minutes.
 */

export interface BookingDraft {
  doctor: Doctor | null;
  clinic: Clinic | null;
  procedure: Procedure | null;
  slot: Availability | null;
  notes: string;
  /** When the server-side hold on `slot` expires (set when the patient continues to payment). */
  heldUntil: string | null;
}

const emptyDraft: BookingDraft = { doctor: null, clinic: null, procedure: null, slot: null, notes: "", heldUntil: null };

interface BookingContextValue {
  draft: BookingDraft;
  setDraft: (updater: (prev: BookingDraft) => BookingDraft) => void;
  resetDraft: () => void;
}

const BookingContext = createContext<BookingContextValue | undefined>(undefined);

export function BookingProvider({ children }: { children: ReactNode }) {
  const [draft, setDraftState] = useState<BookingDraft>(emptyDraft);

  // Stable identities, so consumers can list them as effect dependencies.
  const setDraft = useCallback((updater: (prev: BookingDraft) => BookingDraft) => setDraftState(updater), []);
  const resetDraft = useCallback(() => setDraftState(emptyDraft), []);
  const value = useMemo(() => ({ draft, setDraft, resetDraft }), [draft, setDraft, resetDraft]);

  return <BookingContext.Provider value={value}>{children}</BookingContext.Provider>;
}

export function useBookingContext(): BookingContextValue {
  const ctx = useContext(BookingContext);
  if (!ctx) throw new Error("useBookingContext must be used within BookingProvider");
  return ctx;
}
