/**
 * Base API client.
 *
 * Design decision: one thin wrapper around `fetch`, used by every
 * feature-specific service module (see services/). No component ever
 * calls `fetch` directly.
 *
 * Why: centralizes the API base URL, default headers, error handling,
 * and (starting Sprint 2) auth token attachment, in one place. If we
 * later swap to a generated client from an OpenAPI spec, only this file
 * and the services/ modules change — page/component code is unaffected.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new ApiError(response.status, body || response.statusText);
  }

  return response.json() as Promise<T>;
}
