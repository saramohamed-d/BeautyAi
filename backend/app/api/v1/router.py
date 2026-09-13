from fastapi import APIRouter

from app.api.v1.appointments import router as appointments_router
from app.api.v1.availability import router as availability_router
from app.api.v1.clinics import router as clinics_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.doctors import router as doctors_router
from app.api.v1.health import router as health_router
from app.api.v1.intakes import router as intakes_router
from app.api.v1.patients import router as patients_router
from app.api.v1.procedures import router as procedures_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(patients_router)
api_router.include_router(doctors_router)
api_router.include_router(clinics_router)
api_router.include_router(procedures_router)
api_router.include_router(availability_router)
api_router.include_router(appointments_router)
api_router.include_router(conversations_router)
api_router.include_router(intakes_router)
