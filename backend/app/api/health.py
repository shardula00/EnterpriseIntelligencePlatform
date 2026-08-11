"""Health check endpoint.

Reports both application liveness and database connectivity, so a green
response is actually evidence the whole local stack (FastAPI -> SQLAlchemy
-> Postgres) is wired together correctly - not just that the process is up.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    app_name: str
    app_env: str
    database: str


@router.get("/health", response_model=HealthResponse)
def health_check(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    try:
        db.execute(text("SELECT 1"))
        database_status = "connected"
    except Exception:
        database_status = "error"

    return HealthResponse(
        status="ok" if database_status == "connected" else "degraded",
        app_name=settings.app_name,
        app_env=settings.app_env,
        database=database_status,
    )
