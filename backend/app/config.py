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
_DEFAULT_ML_ARTIFACTS_DIR = _REPO_ROOT / "data" / "ml_artifacts"


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

    # ML (Phase 5). Trained model artifacts (joblib files) are retained here
    # for provenance/reproducibility, same pattern as upload_storage_dir -
    # never committed to git.
    ml_artifacts_dir: Path = _DEFAULT_ML_ARTIFACTS_DIR
    # A fixed default seed makes training reproducible when a caller doesn't
    # supply their own. A safety cap on training rows keeps this a local
    # student-project workload, not something that can accidentally take
    # minutes on a huge upload; datasets above the cap are randomly
    # downsampled (with the same seed) and that fact is recorded in the run's
    # configuration, never silently hidden.
    ml_default_random_seed: int = 42
    ml_max_training_rows: int = 50_000

    # MLOps (Phase 6). Drift is measured via PSI (Population Stability
    # Index), a standard, widely-used credit-risk/MLOps monitoring statistic
    # - these are its conventional published thresholds, not values invented
    # for this project. See app/mlops/drift.py for the full explanation.
    drift_psi_warning_threshold: float = 0.1
    drift_psi_severe_threshold: float = 0.25
    # Relative (not absolute) change in a model's primary metric vs. its
    # recorded training-time baseline. 5%/15% are deliberately simple,
    # documented defaults (see app/mlops/monitoring.py) - not a
    # statistically derived significance level, since that would need a
    # sampling distribution this project doesn't have the data to estimate.
    performance_degradation_warning_threshold: float = 0.05
    performance_degradation_severe_threshold: float = 0.15


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor.

    Cached so we parse the environment once per process; FastAPI's
    dependency-injection can still override this in tests via
    `app.dependency_overrides`.
    """
    return Settings()
