"""Decision Intelligence: recommendations and their human-approval
lifecycle (Phase 11).

Unlike every prior phase's persistence (RagQuery, AnalyticsQuery, MLRun -
all write-once), a Recommendation is this project's first *stateful*
object: created as "pending," then later mutated to "approved"/"rejected"
by a separate request. That lifecycle is the actual reason this table
exists - see app/decision/__init__.py for why nothing else in Phase 11
needed new persistence (scenario calculations stay stateless).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # CASCADE: a recommendation about a dataset is meaningless once that
    # dataset is gone - same reasoning as every other dataset_id-FK'd
    # table in this project (MLRun, AnalyticsQuery, kg.Entity).
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    question: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)

    # Heterogeneous small lists - JSONB, same convention as RagQuery.sources/
    # AnalyticsQuery.rows/MLRun.results: the shape is naturally per-item,
    # not a fixed relational schema, and never queried by individual field.
    alternatives: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # Each item: {"agent": str, "tool": str, "summary": str, "data": dict|None}
    # - the *actual* ToolOutcome objects Phase 10's agents already produced,
    # never re-derived or restated as independently verified.
    evidence: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # Risk agent's own RiskFlag dicts, verbatim - never a second risk
    # representation invented here (see app/agents/risk_agent.py).
    risks: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # Explicit strings naming anything not directly verified.
    assumptions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # "low" | "medium" | "high" - a coarse, deterministically-derived
    # label (see app/decision/recommendation.py), not a calibrated
    # statistic.
    confidence: Mapped[str] = mapped_column(String(10), nullable=False)

    # Null (with an explanation folded into `assumptions`/the scenario's
    # own `reason`) when no quantifiable what-if scenario was computed -
    # never a fabricated number. See app/decision/scenario.py.
    expected_impact: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # "pending" | "approved" | "rejected" - nothing is ever treated as
    # acted-on merely because a Recommendation row exists; only a human
    # explicitly changing this via POST /decisions/{id}/approve|reject
    # does that (see app/api/decisions.py).
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
