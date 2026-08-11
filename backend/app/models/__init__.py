"""ORM models.

Every model must be imported here so that Alembic's autogenerate can see it
via `Base.metadata` (see backend/migrations/env.py).
"""

from app.models.app_metadata import AppMetadata
from app.models.audit import AuditLog
from app.models.dataset import Dataset, DatasetColumn, DatasetLineageEvent, DatasetQualityIssue
from app.models.user import Permission, Role, RolePermission, User, UserRole

__all__ = [
    "AppMetadata",
    "AuditLog",
    "Dataset",
    "DatasetColumn",
    "DatasetLineageEvent",
    "DatasetQualityIssue",
    "Permission",
    "Role",
    "RolePermission",
    "User",
    "UserRole",
]
