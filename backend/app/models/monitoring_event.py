"""Monitoring/alerting persistence (Phase 6).

One row per drift check or performance-monitoring check ever run - this is
the "alert" record, deliberately separate from `audit_logs`: audit_logs
answers "who did what security/administration-relevant action," while this
table answers "what did the monitoring engine detect." A drift check still
also writes one audit_logs row (see app/api/mlops.py), matching the same
dual-write pattern Phase 5 established for training (an MLRun row +
an audit event) - this table is the "what," audit_logs is the "who."

`severity` is a normalized 3-value field (info/warning/critical) shared by
both event types, independent of each domain's own richer status vocabulary
(drift's stable/warning/drift, monitoring's stable/warning/degraded) held in
`details` - so a future alert channel (email/Slack) can render a consistent
inbox from `severity` alone without knowing about drift-specific or
monitoring-specific status names.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

EVENT_TYPES = ("drift", "performance_monitoring")
SEVERITIES = ("info", "warning", "critical")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class MonitoringEvent(Base):
    __tablename__ = "ml_monitoring_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    model_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("model_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # The dataset the check was run *against* (the "new"/reference data) -
    # not necessarily the model's original training dataset.
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)

    # Full structured result (per-feature drift table, or the
    # baseline/current metric comparison) - same "store the whole payload as
    # JSONB" pattern as MLRun.results.
    details: Mapped[dict] = mapped_column(JSONB, nullable=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False, index=True)
