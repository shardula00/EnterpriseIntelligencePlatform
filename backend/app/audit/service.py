"""Audit event recording and querying - pure DB logic, no HTTP.

record_event() takes plain ip_address/user_agent strings rather than a
FastAPI Request object, so this module (like ingestion/service.py and
bi/service.py) has no framework dependency; the API layer is responsible
for pulling those two values off the request.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.user import User


class AuditAction:
    """Canonical action strings - use these constants, not ad hoc literals,
    so filtering/querying the log is reliable."""

    USER_REGISTERED = "user.registered"
    LOGIN_SUCCESS = "auth.login.success"
    LOGIN_FAILED = "auth.login.failed"
    LOGOUT = "auth.logout"
    DATASET_UPLOADED = "dataset.uploaded"
    DATASET_DELETED = "dataset.deleted"
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_ACTIVATED = "user.activated"
    USER_DEACTIVATED = "user.deactivated"
    USER_DELETED = "user.deleted"
    USER_ROLE_CHANGED = "user.role_changed"
    ML_MODEL_TRAINED = "ml.model_trained"
    MODEL_VERSION_REGISTERED = "mlops.model_version_registered"
    MODEL_VERSION_PROMOTED = "mlops.model_version_promoted"
    MODEL_VERSION_ARCHIVED = "mlops.model_version_archived"
    DRIFT_CHECK_RUN = "mlops.drift_check_run"
    PERFORMANCE_CHECK_RUN = "mlops.performance_check_run"
    DOCUMENT_UPLOADED = "rag.document_uploaded"
    DOCUMENT_PROCESSED = "rag.document_processed"
    DOCUMENT_PROCESSING_FAILED = "rag.document_processing_failed"
    DOCUMENT_DELETED = "rag.document_deleted"
    RAG_QUERY_PERFORMED = "rag.query_performed"
    ANALYTICS_QUERY_PERFORMED = "analytics.query_performed"
    KG_BUILT = "kg.graph_built"
    AGENT_RUN_PERFORMED = "agents.run_performed"


# Case-insensitive metadata keys that are never written, no matter what a
# caller passes in - a last line of defense on top of callers already being
# expected to never pass these.
_NEVER_LOG_KEYS = {
    "password",
    "password_hash",
    "token",
    "access_token",
    "refresh_token",
    "jwt",
    "secret",
    "authorization",
}


def _scrub_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    if not metadata:
        return None
    return {k: v for k, v in metadata.items() if k.lower() not in _NEVER_LOG_KEYS}


def record_event(
    db: Session,
    *,
    user_id: uuid.UUID | None,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Add one audit log row to the current transaction.

    Does not commit - callers include this as part of the same transaction
    as the action being recorded (e.g. dataset deletion), so the audit
    trail and the action it describes are never inconsistent with each
    other. Truncates user_agent defensively since browsers can send long
    strings.
    """
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            event_metadata=_scrub_metadata(metadata),
            ip_address=ip_address,
            user_agent=(user_agent[:500] if user_agent else None),
        )
    )


@dataclass
class AuditLogEntry:
    id: int
    user_id: uuid.UUID | None
    user_email: str | None
    action: str
    resource_type: str | None
    resource_id: str | None
    event_metadata: dict[str, Any] | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime


def list_audit_logs(
    db: Session,
    *,
    limit: int = 50,
    offset: int = 0,
    action: str | None = None,
    resource_type: str | None = None,
    user_id: uuid.UUID | None = None,
) -> tuple[list[AuditLogEntry], int]:
    stmt = select(AuditLog, User.email).outerjoin(User, AuditLog.user_id == User.id)

    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    if resource_type is not None:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)

    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = db.execute(count_stmt).scalar_one()

    # created_at alone isn't a reliable sort key: it's set client-side via
    # datetime.now(), so two events recorded in quick succession (e.g. two
    # commits in the same request/test) can tie at the clock's resolution.
    # id is monotonically increasing with insertion order, so it's used as
    # the tiebreaker to keep "newest first" deterministic.
    rows = db.execute(
        stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit).offset(offset)
    ).all()
    entries = [
        AuditLogEntry(
            id=log.id,
            user_id=log.user_id,
            user_email=email,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            event_metadata=log.event_metadata,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            created_at=log.created_at,
        )
        for log, email in rows
    ]
    return entries, total
