"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.datasets import router as datasets_router
from app.api.health import router as health_router
from app.api.kpis import router as kpis_router
from app.api.ml import router as ml_router
from app.api.mlops import router as mlops_router
from app.api.users import catalog_router as users_catalog_router
from app.api.users import router as users_router
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
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(users_catalog_router)
app.include_router(audit_router)
app.include_router(datasets_router)
app.include_router(kpis_router)
app.include_router(ml_router)
app.include_router(mlops_router)
