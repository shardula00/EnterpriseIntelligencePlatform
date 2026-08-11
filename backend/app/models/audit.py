"""Audit log model (Phase 4).

One append-only table for every security/administration-relevant event.
`resource_id` is deliberately a plain string, not a foreign key - an audit
record must remain readable after the thing it describes is deleted (a
dataset, a user, ...), so it's a soft reference by design, same as
`DatasetQualityIssue.column_name` already is elsewhere in this codebase.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # SET NULL (not CASCADE): deleting a user must not erase their history.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Structured extra detail. Never passwords/hashes/tokens/secrets - see
    # app/audit/service.py's docstring for the exact rule enforced there.
    event_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)  # fits IPv6
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False, index=True)
