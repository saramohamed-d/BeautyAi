const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const AUTH_PREFIX = "/api/v1/auth";

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(status: number, message: string, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
    this.name = "ApiError";
  }
}

/*
 * Access token handling.
 *
 * The access token lives only in this module's memory — never in
 * localStorage or a readable cookie, so injected scripts can't lift it
 * from storage. The refresh token is an httpOnly cookie the browser only
 * sends to /api/v1/auth; `lib/auth-context.tsx` uses it to restore the
 * session on page load and registers the refresh handler below so an
 * expired access token is renewed transparently.
 */
let accessToken: string | null = null;
let refreshHandler: (() => Promise<string | null>) | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function setRefreshHandler(handler: (() => Promise<string | null>) | null): void {
  refreshHandler = handler;
}

async function toApiError(response: Response): Promise<ApiError> {
  const body = await response.text().catch(() => "");
  let message = response.statusText;
  let code: string | undefined;

  try {
    const parsed = JSON.parse(body);
    if (typeof parsed === "object" && parsed !== null) {
      // The backend's AppError handler returns {"error": {"code", "message"}}
      // (see backend/app/main.py); FastAPI's own errors use {"detail": ...}.
      const source = typeof parsed.error === "object" && parsed.error !== null ? parsed.error : parsed;
      message =
        typeof source.message === "string"
          ? source.message
          : typeof parsed.detail === "string"
            ? parsed.detail
            : message;
      code = typeof source.code === "string" ? source.code : undefined;
    }
  } catch {
    if (body) message = body;
  }
  return new ApiError(response.status, message, code);
}

/** One request, with the access token attached and one silent retry after a refresh. */
async function request(path: string, init?: RequestInit, retryOnExpiredToken = true): Promise<Response> {
  const isAuthEndpoint = path.startsWith(AUTH_PREFIX);
  const sentToken = accessToken;

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    // The refresh cookie is only needed (and only sent) for /auth calls.
    credentials: isAuthEndpoint ? "include" : "omit",
    headers: {
      // FormData sets its own multipart boundary; forcing JSON would break it.
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(sentToken ? { Authorization: `Bearer ${sentToken}` } : {}),
      ...init?.headers,
    },
  });

  if (response.status === 401 && sentToken && !isAuthEndpoint && retryOnExpiredToken && refreshHandler) {
    const renewed = await refreshHandler();
    if (renewed) return request(path, init, false);
  }

  if (!response.ok) throw await toApiError(response);
  return response;
}

export async function apiFetch<T>(path: string, init?: RequestInit, retryOnExpiredToken = true): Promise<T> {
  const response = await request(path, init, retryOnExpiredToken);
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

/** For files (verification documents): the same auth, but the body stays binary. */
export async function apiFetchBlob(path: string): Promise<Blob> {
  return (await request(path)).blob();
}

export function buildQuery<T extends object>(params: T): string {
  const searchParams = new URLSearchParams();

  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") {
      continue;
    }

    if (Array.isArray(value)) {
      for (const item of value) {
        if (item !== undefined && item !== null && item !== "") {
          searchParams.append(key, String(item));
        }
      }
    } else {
      searchParams.set(key, String(value));
    }
  }

  const query = searchParams.toString();

  return query ? `?${query}` : "";
}
