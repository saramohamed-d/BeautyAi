"""
Request rate limiting (Sprint 17; docs/security.md).

Design decisions:

- **Fixed windows in Redis**, keyed by what we're protecting plus the
  caller's IP (and, where it matters, the identifier they're trying).
  Simple, cheap, and good enough to stop password guessing and sign-up
  floods; it is not a defence against a distributed attack, which belongs
  at the edge (nginx / Cloudflare — see docs/deployment.md).
- **A broken limiter must not break the site, but it shouldn't disappear
  either.** If Redis is unreachable the limiter falls back to counting in
  this process: weaker than a shared counter (each worker counts its own
  share), still far better than no limit at all, and it never locks
  anyone out because a cache is down.
- **Limits are per endpoint group**, not global, so a patient hammering
  the chat can't lock themselves out of logging in.
- The AI chat keeps its own hourly limit per patient (Sprint 7), which is
  about cost and abuse of the model rather than credential attacks.
"""

import time
from collections import defaultdict
from collections.abc import Callable

from fastapi import Depends, Request
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.exceptions import TooManyRequestsError
from app.core.logging import get_logger

logger = get_logger(__name__)

_redis: Redis | None = None
# Fallback counters: {bucket:key: [timestamps]}. Per process, so N workers
# allow up to N times the limit — deliberately simple, and only in use
# while Redis is unavailable.
_local: dict[str, list[float]] = defaultdict(list)


async def get_redis() -> Redis | None:
    """One client for the process; None when Redis can't be reached."""
    global _redis
    if _redis is None:
        try:
            _redis = Redis.from_url(get_settings().redis_url, socket_timeout=1, socket_connect_timeout=1)
        except Exception as exc:  # pragma: no cover - construction rarely fails
            logger.warning("rate_limit.redis_unavailable", error=type(exc).__name__)
            return None
    return _redis


async def reset() -> None:
    """Drops the cached client and counters (tests, and after a config change)."""
    global _redis
    _local.clear()
    if _redis is not None:
        await _redis.aclose()
        _redis = None


def _hit_locally(window_key: str, *, times: int, seconds: int) -> bool:
    now = time.monotonic()
    recent = [stamp for stamp in _local[window_key] if now - stamp < seconds]
    recent.append(now)
    _local[window_key] = recent
    return len(recent) <= times


def client_ip(request: Request) -> str:
    """
    The caller's address.

    Behind the reverse proxy the real address is the first entry of
    `X-Forwarded-For`; the proxy is trusted to set it (nginx config in
    docs/deployment.md). Falling back to the socket address keeps this
    working when the app is exposed directly.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def hit(bucket: str, key: str, *, times: int, seconds: int) -> bool:
    """Counts one request. Returns False when the window is already full."""
    if not get_settings().rate_limit_enabled:
        return True
    window_key = f"ratelimit:{bucket}:{key}"
    redis = await get_redis()
    if redis is not None:
        try:
            count = await redis.incr(window_key)
            if count == 1:
                await redis.expire(window_key, seconds)
            return count <= times
        except Exception as exc:
            # Redis down: keep limiting in this process rather than not at all.
            logger.warning("rate_limit.degraded", bucket=bucket, error=type(exc).__name__)
    return _hit_locally(window_key, times=times, seconds=seconds)


def limit(bucket: str, *, times: int, seconds: int) -> Callable:
    """
    FastAPI dependency: `Depends(limit("login", times=10, seconds=300))`.

    429 with `rate_limited` and a `Retry-After` header when the window is
    full, which is the same error shape as the chat's hourly limit.
    """

    async def dependency(request: Request) -> None:
        if not await hit(bucket, client_ip(request), times=times, seconds=seconds):
            logger.info("rate_limit.blocked", bucket=bucket, ip=client_ip(request))
            raise TooManyRequestsError(
                "Too many attempts. Please wait a few minutes and try again.",
            )

    return Depends(dependency)
