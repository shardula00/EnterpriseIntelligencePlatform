"""Pydantic response models for the audit log API."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: int
    user_id: UUID | None
    user_email: str | None
    action: str
    resource_type: str | None
    resource_id: str | None
    event_metadata: dict[str, Any] | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime


class AuditLogPage(BaseModel):
    items: list[AuditLogOut]
    total: int
    limit: int
    offset: int
