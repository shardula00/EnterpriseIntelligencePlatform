"""Model registry persistence (Phase 6).

A ModelVersion is a *lifecycle wrapper* around an existing MLRun - it never
duplicates MLRun's `configuration`/`results` (training config, feature
columns, metrics all already live there). This is a deliberate choice: a
model version's config/metrics should have exactly one source of truth, and
re-fetching via `ml_run_id` costs one cheap join, not a sync-drift risk.
What a ModelVersion adds that MLRun doesn't have is *governance* state:
where this run sits in candidate -> staging -> production -> archived, who
put it there, and when.

"Model family": versions are numbered per (dataset_id, task_type) - the
same task trained on a different dataset is a different family (e.g. a
churn classifier for Dataset A and one for Dataset B don't compete for the
same "production" slot). dataset_id/task_type are denormalized from the
linked MLRun purely so the registry can list/filter/group without a join
on every request - see app/ml/service.py's MLRun for the same pattern.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# candidate: just registered, not yet trusted for anything.
# staging: passed a human's first look, being evaluated before production.
# production: the version actually meant to be used right now.
# archived: retired - terminal in this implementation (see registry_service.py
# for the deliberately simplified state machine and why "archived" isn't
# reversible here).
LIFECYCLE_STATUSES = ("candidate", "staging", "production", "archived")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = (
        UniqueConstraint(
            "dataset_id", "task_type", "version_number", name="uq_model_version_family_number"
        ),
        # Belt-and-suspenders DB-level guarantee alongside registry_service.py's
        # application-level auto-archive-on-promote logic: at most one
        # "production" row per (dataset_id, task_type) family, ever, even if a
        # future code path forgets to enforce it.
        Index(
            "uq_model_version_one_production_per_family",
            "dataset_id",
            "task_type",
            unique=True,
            postgresql_where=text("status = 'production'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # One version per run - a run is registered at most once.
    ml_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ml_runs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Denormalized from the linked MLRun (see module docstring).
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)

    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="candidate", index=True)

    # sha256 of the artifact file at registration time - lets a caller later
    # confirm the artifact on disk hasn't changed/corrupted since this
    # version pointed at it.
    artifact_checksum: Mapped[str] = mapped_column(String(64), nullable=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)

    promoted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    promoted_at: Mapped[datetime | None] = mapped_column(nullable=True)
