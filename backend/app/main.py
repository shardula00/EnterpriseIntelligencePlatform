"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.datasets import router as datasets_router
from app.api.health import router as health_router
from app.api.kpis import router as kpis_router
from app.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name)

# Phase 3: the React dev server runs on a different origin than the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, tags=["health"])
app.include_router(datasets_router)
app.include_router(kpis_router)
