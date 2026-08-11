"""A small key/value table for platform-level metadata.

This is the first real table in the system - used for things like
recording schema/seed versions or last-maintenance timestamps in later
phases. It exists in Phase 1 to give the first Alembic migration a real
table to create, rather than a throwaway one.
"""

from datetime import UTC, datetime

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AppMetadata(Base):
    __tablename__ = "app_metadata"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=_utcnow, onupdate=_utcnow, nullable=False
    )
