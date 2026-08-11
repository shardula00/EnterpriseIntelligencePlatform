"""ORM models.

Every model must be imported here so that Alembic's autogenerate can see it
via `Base.metadata` (see backend/migrations/env.py).
"""

from app.models.app_metadata import AppMetadata

__all__ = ["AppMetadata"]
