"""
Health check endpoint.

Design decision: the health check actively pings Postgres and Redis
rather than just returning "ok" unconditionally.

Why: a health endpoint that always says "ok" is useless for orchestration
(Docker healthchecks, k8s liveness/readiness probes, load balancers) and
useless for debugging ("is the API even reachable, or is it reachable
but the DB is down?"). Checking real dependencies here means Sprint 20's
production deployment can wire this straight into infra health checks
with no changes.

This endpoint intentionally does NOT require authentication — health
checks need to be reachable by infrastructure before a user/service
identity exists.
"""

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.db.session import get_db
from app.schemas.health import ComponentStatus, HealthResponse

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


@router.get("/health", response_model=HealthResponse)
async def health_check(
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    components: list[ComponentStatus] = []

    # --- Postgres ---
    try:
        await db.execute(text("SELECT 1"))
        components.append(ComponentStatus(name="postgres", status="ok"))
    except Exception as exc:  # noqa: BLE001 - health check must not raise
        logger.error("health_check.postgres_failed", error=str(exc))
        components.append(ComponentStatus(name="postgres", status="error", detail=str(exc)))

    # --- Redis ---
    redis_client: Redis | None = None
    try:
        redis_client = Redis.from_url(settings.redis_url)
        await redis_client.ping()
        components.append(ComponentStatus(name="redis", status="ok"))
    except Exception as exc:  # noqa: BLE001
        logger.error("health_check.redis_failed", error=str(exc))
        components.append(ComponentStatus(name="redis", status="error", detail=str(exc)))
    finally:
        if redis_client is not None:
            await redis_client.aclose()

    overall = "ok" if all(c.status == "ok" for c in components) else "degraded"

    return HealthResponse(status=overall, app_env=settings.app_env, components=components)
