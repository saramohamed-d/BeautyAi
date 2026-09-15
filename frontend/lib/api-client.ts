const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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

    let message = response.statusText;
    let code: string | undefined;

    try {
      const parsed = JSON.parse(body);

      if (typeof parsed === "object" && parsed !== null) {
        message =
          typeof parsed.detail === "string"
            ? parsed.detail
            : typeof parsed.message === "string"
              ? parsed.message
              : message;

        code = typeof parsed.code === "string" ? parsed.code : undefined;
      }
    } catch {
      if (body) {
        message = body;
      }
    }

    throw new ApiError(response.status, message, code);
  }

  return response.json() as Promise<T>;
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