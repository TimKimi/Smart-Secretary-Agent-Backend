from fastapi import APIRouter

from src.ssa.api.v1.health import router as health_router

api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
