"""
Aggregates all /api/v1/* routers.

Design decision: each resource (health, and later auth, chat, doctors,
clinics, appointments, ...) gets its own module under app/api/v1/, each
exposing an `APIRouter`. This file is the only place that assembles them
into one router mounted onto the app in main.py.

Why: keeps main.py stable as the API grows — adding a new resource in
Sprint 2+ means adding one `include_router` line here, not touching
main.py or any other route module.
"""

from fastapi import APIRouter

from app.api.v1.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
