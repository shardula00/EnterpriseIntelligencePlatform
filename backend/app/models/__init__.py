"""ORM models.

Every model must be imported here so that Alembic's autogenerate can see it
via `Base.metadata` (see backend/migrations/env.py).
"""

from app.models.analytics import AnalyticsQuery
from app.models.app_metadata import AppMetadata
from app.models.audit import AuditLog
from app.models.dataset import Dataset, DatasetColumn, DatasetLineageEvent, DatasetQualityIssue
from app.models.document import Document, DocumentChunk, RagQuery
from app.models.kg import Entity, Relationship
from app.models.ml_run import MLRun
from app.models.model_version import ModelVersion
from app.models.monitoring_event import MonitoringEvent
from app.models.user import Permission, Role, RolePermission, User, UserRole

__all__ = [
    "AnalyticsQuery",
    "AppMetadata",
    "AuditLog",
    "Dataset",
    "DatasetColumn",
    "DatasetLineageEvent",
    "DatasetQualityIssue",
    "Document",
    "DocumentChunk",
    "Entity",
    "MLRun",
    "ModelVersion",
    "MonitoringEvent",
    "Permission",
    "RagQuery",
    "Relationship",
    "Role",
    "RolePermission",
    "User",
    "UserRole",
]
