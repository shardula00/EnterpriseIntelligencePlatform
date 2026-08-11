"""Application configuration.

Settings are loaded from environment variables (and, for local development,
from a `.env` file in `backend/`). Nothing here should ever contain a real
secret - `.env` is gitignored, and `.env.example` documents the shape
without real values.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> backend/app -> backend -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_UPLOAD_STORAGE_DIR = _REPO_ROOT / "data" / "raw" / "uploads"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Enterprise Intelligence Platform"
    app_env: str = "local"
    log_level: str = "INFO"

    database_url: str = (
        "postgresql+psycopg://eip_user:eip_dev_password@localhost:5432/eip_dev"
    )

    # Ingestion (Phase 2). Original uploaded files are retained here for
    # provenance/lineage - never committed to git (see .gitignore).
    upload_storage_dir: Path = _DEFAULT_UPLOAD_STORAGE_DIR
    max_upload_size_mb: int = 50

    # Frontend (Phase 3). The Vite dev server runs on a different origin
    # than the API, so the browser needs an explicit CORS allow-list rather
    # than a wildcard.
    cors_allow_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Auth (Phase 4). This default is only safe for local development - it's
    # deliberately obvious so nobody mistakes it for a real secret. Anyone
    # deploying this beyond a local machine must set a real JWT_SECRET_KEY.
    jwt_secret_key: str = "CHANGE-ME-THIS-IS-A-LOCAL-DEV-ONLY-DEFAULT-SECRET"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60

    # Bootstrap admin (Phase 4). Read only by scripts/bootstrap_admin.py -
    # never used as a fallback/default password. No default value for the
    # password: bootstrap_admin.py refuses to run if it's unset.
    bootstrap_admin_email: str = "admin@example.com"
    bootstrap_admin_password: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor.

    Cached so we parse the environment once per process; FastAPI's
    dependency-injection can still override this in tests via
    `app.dependency_overrides`.
    """
    return Settings()
