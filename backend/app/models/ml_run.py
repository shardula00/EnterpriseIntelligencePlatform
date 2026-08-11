"""ML run persistence (Phase 5).

One row per completed training run - no separate results/predictions
table (see app/ml/__init__.py: results are computed on demand from the
persisted artifact, and a full results payload is stored right here in
`results`, not just headline metrics - the field is named for what it
holds, a small deviation from "metrics JSONB" as originally sketched).

dataset_id CASCADEs on delete - unlike audit_logs (which must survive the
thing they describe being deleted, by design), an ML run is meaningless
without its source dataset, so it's cleaned up alongside it.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class MLRun(Base):
    __tablename__ = "ml_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    # Always "completed" for now - training is synchronous end to end. The
    # column exists so Phase 6 can introduce async job execution ("running",
    # "failed") without a schema change.
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)

    configuration: Mapped[dict] = mapped_column(JSONB, nullable=False)
    results: Mapped[dict] = mapped_column(JSONB, nullable=False)

    artifact_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # SET NULL, not CASCADE: a run's history is still meaningful after the
    # user who trained it is deleted, same reasoning as audit_logs.user_id.
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
