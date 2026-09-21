/**
 * Validates a `?next=` redirect target. Only same-site paths are allowed,
 * so a crafted link can't bounce someone to another site after login
 * ("//evil.com" and "/\evil.com" are protocol-relative in browsers).
 */
export function safeNext(value: string | null | undefined, fallback = "/"): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) return fallback;
  return value;
}

/** Builds a login/signup link that returns to `next` afterwards. */
export function withNext(path: "/login" | "/signup", next: string | null | undefined): string {
  const target = safeNext(next, "");
  return target ? `${path}?next=${encodeURIComponent(target)}` : path;
}
