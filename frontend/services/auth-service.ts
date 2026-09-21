import { apiFetch } from "@/lib/api-client";
import type { DoctorRegisterInput, Me, RegisterInput, SessionResponse } from "@/types/auth";

export function login(identifier: string, password: string): Promise<SessionResponse> {
  return apiFetch<SessionResponse>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ identifier, password }),
  });
}

export function register(input: RegisterInput): Promise<SessionResponse> {
  return apiFetch<SessionResponse>("/api/v1/auth/register", { method: "POST", body: JSON.stringify(input) });
}

/** "Join as a Doctor": creates the login and the unverified profile. */
export function registerDoctor(input: DoctorRegisterInput): Promise<SessionResponse> {
  return apiFetch<SessionResponse>("/api/v1/auth/register/doctor", { method: "POST", body: JSON.stringify(input) });
}

let refreshInFlight: Promise<SessionResponse> | null = null;

/**
 * Exchanges the refresh cookie for a new session. Concurrent callers
 * share one request: each refresh rotates the cookie, so parallel
 * refreshes from one tab would otherwise race each other.
 */
export function refreshSession(): Promise<SessionResponse> {
  refreshInFlight ??= apiFetch<SessionResponse>("/api/v1/auth/refresh", { method: "POST" }).finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}

export function logout(): Promise<void> {
  return apiFetch<void>("/api/v1/auth/logout", { method: "POST" });
}

// --- Password reset, verification and data rights (Sprint 17) ---------------

export function forgotPassword(identifier: string): Promise<{ message: string }> {
  return apiFetch<{ message: string }>("/api/v1/auth/password/forgot", {
    method: "POST",
    body: JSON.stringify({ identifier }),
  });
}

export function resetPassword(token: string, password: string): Promise<{ message: string }> {
  return apiFetch<{ message: string }>("/api/v1/auth/password/reset", {
    method: "POST",
    body: JSON.stringify({ token, password }),
  });
}

export function requestVerification(channel: "email" | "phone" = "email"): Promise<{ message: string }> {
  return apiFetch<{ message: string }>("/api/v1/auth/verify/request", {
    method: "POST",
    body: JSON.stringify({ channel }),
  });
}

export function confirmVerification(code: string, channel: "email" | "phone" = "email"): Promise<Me> {
  return apiFetch<Me>("/api/v1/auth/verify/confirm", { method: "POST", body: JSON.stringify({ channel, code }) });
}

/** Everything the platform holds about the signed-in person (PDPL right of access). */
export function exportMyData(): Promise<Record<string, unknown>> {
  return apiFetch<Record<string, unknown>>("/api/v1/auth/me/data");
}

export function deleteMyAccount(password: string): Promise<{ message: string; kept: Record<string, number> }> {
  return apiFetch<{ message: string; kept: Record<string, number> }>("/api/v1/auth/me/delete", {
    method: "POST",
    body: JSON.stringify({ password }),
  });
}
