"""
FastAPI application entrypoint.

Design decision: main.py only does application *wiring* — creating the
FastAPI instance, configuring middleware, and mounting routers. No
business logic, no route handlers, live here.

Why: this is the "composition root" of the backend. Keeping it thin means
anyone new to the codebase can read this one file top-to-bottom and
understand exactly what the app is made of, then go look at the relevant
module (api/, core/, db/) for details.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup/shutdown hook.

    Sprint 0 only logs a startup/shutdown message. Later sprints will use
    this to, e.g., warm up the embeddings client or verify required
    external services are reachable before accepting traffic.
    """
    logger.info("app.startup", app_env=settings.app_env)
    yield
    logger.info("app.shutdown")


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)

# CORS: the Next.js frontend runs on a different origin during local dev
# (localhost:3000 vs localhost:8000), so the browser will block requests
# without explicit CORS headers. Origins are configurable per environment
# via settings.cors_origins rather than hardcoded here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": settings.app_name, "status": "running"}
