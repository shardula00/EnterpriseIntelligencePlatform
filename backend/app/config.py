"""Application configuration.

Settings are loaded from environment variables (and, for local development,
from a `.env` file in `backend/`). Nothing here should ever contain a real
secret - `.env` is gitignored, and `.env.example` documents the shape
without real values.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Enterprise Intelligence Platform"
    app_env: str = "local"
    log_level: str = "INFO"

    database_url: str = (
        "postgresql+psycopg://eip_user:eip_dev_password@localhost:5432/eip_dev"
    )


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor.

    Cached so we parse the environment once per process; FastAPI's
    dependency-injection can still override this in tests via
    `app.dependency_overrides`.
    """
    return Settings()
