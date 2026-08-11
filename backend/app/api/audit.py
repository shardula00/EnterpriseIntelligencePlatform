"""Audit log API: read-only, admin/auditor-only (audit:read)."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.audit.schemas import AuditLogOut, AuditLogPage
from app.audit.service import list_audit_logs
from app.db import get_db
from app.models.user import User
from app.rbac.dependencies import require_permission

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=AuditLogPage)
def get_audit_logs(
    limit: int = 50,
    offset: int = 0,
    action: str | None = None,
    resource_type: str | None = None,
    user_id: UUID | None = None,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("audit:read")),
) -> AuditLogPage:
    entries, total = list_audit_logs(
        db,
        limit=limit,
        offset=offset,
        action=action,
        resource_type=resource_type,
        user_id=user_id,
    )
    return AuditLogPage(
        items=[
            AuditLogOut(
                id=e.id,
                user_id=e.user_id,
                user_email=e.user_email,
                action=e.action,
                resource_type=e.resource_type,
                resource_id=e.resource_id,
                event_metadata=e.event_metadata,
                ip_address=e.ip_address,
                user_agent=e.user_agent,
                created_at=e.created_at,
            )
            for e in entries
        ],
        total=total,
        limit=limit,
        offset=offset,
    )
