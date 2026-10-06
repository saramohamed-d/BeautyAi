"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { setAccessToken, setRefreshHandler } from "@/lib/api-client";
import { audienceOf, type Audience } from "@/lib/roles";
import * as authService from "@/services/auth-service";
import type { AuthUser, DoctorRegisterInput, Me, RegisterInput, SessionResponse } from "@/types/auth";
import type { ClinicMembership } from "@/types/clinic";
import type { Doctor } from "@/types/doctor";
import type { Patient } from "@/types/patient";

type AuthStatus = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  status: AuthStatus;
  user: AuthUser | null;
  /** The logged-in user's patient profile (null for staff roles and when logged out). */
  patient: Patient | null;
  /** The logged-in user's doctor profile, including its verification status (role=doctor only). */
  doctor: Doctor | null;
  /** Clinics this user administers (role=clinic_admin only). */
  clinics: ClinicMembership[];
  /** Which side of the app this user belongs to ("guest" when logged out); see lib/roles.ts. */
  audience: Audience;
  login: (identifier: string, password: string) => Promise<Me>;
  register: (input: RegisterInput) => Promise<Me>;
  registerDoctor: (input: DoctorRegisterInput) => Promise<Me>;
  /** Re-reads the session after something changed server-side (e.g. an application was submitted). */
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

/**
 * Session state for the whole app.
 *
 * On first load it calls POST /auth/refresh: if the browser still holds
 * a valid refresh cookie the user is logged back in, so a page reload no
 * longer logs anyone out. The access token itself is kept only in memory
 * (see lib/api-client.ts).
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [me, setMe] = useState<Me | null>(null);

  const applySession = useCallback((session: SessionResponse): Me => {
    setAccessToken(session.access_token);
    const next = {
      user: session.user,
      patient: session.patient,
      doctor: session.doctor ?? null,
      clinics: session.clinics ?? [],
    };
    setMe(next);
    setStatus("authenticated");
    return next;
  }, []);

  const clearSession = useCallback(() => {
    setAccessToken(null);
    setMe(null);
    setStatus("anonymous");
    // Drop cached private data (appointments etc.) belonging to the previous user.
    queryClient.removeQueries({ queryKey: ["appointments"] });
  }, [queryClient]);

  // Called by apiFetch when an access token has expired mid-session.
  useEffect(() => {
    setRefreshHandler(async () => {
      try {
        const session = await authService.refreshSession();
        applySession(session);
        return session.access_token;
      } catch {
        clearSession();
        return null;
      }
    });
    return () => setRefreshHandler(null);
  }, [applySession, clearSession]);

  useEffect(() => {
    authService.refreshSession().then(applySession, clearSession);
  }, [applySession, clearSession]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user: me?.user ?? null,
      patient: me?.patient ?? null,
      doctor: me?.doctor ?? null,
      clinics: me?.clinics ?? [],
      audience: audienceOf(me),
      login: async (identifier, password) => applySession(await authService.login(identifier, password)),
      register: async (input) => applySession(await authService.register(input)),
      registerDoctor: async (input) => applySession(await authService.registerDoctor(input)),
      refresh: async () => {
        await authService.refreshSession().then(applySession, clearSession);
      },
      logout: async () => {
        await authService.logout().catch(() => undefined);
        clearSession();
      },
    }),
    [status, me, applySession, clearSession]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
