"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.datasets import router as datasets_router
from app.api.health import router as health_router
from app.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.include_router(health_router, tags=["health"])
app.include_router(datasets_router)
