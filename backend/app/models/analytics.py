"""Natural-language analytics query history (Phase 8).

One row per question asked through POST /analytics/query - the same
"lightweight audit event + richer queryable row" split Phase 5/6/7 already
use (MLRun/ModelVersion/RagQuery vs. AuditLog). `columns`/`rows` are a
JSONB snapshot of the result at query time, capped at
Settings.analytics_max_result_rows - a normalized results table would be
over-structuring data whose shape genuinely differs per question and is
only ever read back as one unit, never queried by its individual fields
(same reasoning as RagQuery.sources).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.dataset import Dataset  # noqa: F401 - referenced by the relationship() below


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AnalyticsQuery(Base):
    __tablename__ = "analytics_queries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # CASCADE, not SET NULL: like MLRun.dataset_id, a result is meaningless
    # without the dataset whose real columns/table it was computed from.
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asked_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    question: Mapped[str] = mapped_column(Text, nullable=False)

    # The rendered SQL text - always derived FROM the SQLAlchemy Core
    # construct that was actually executed (see app/analytics/query_builder.py),
    # never a separate string an LLM produced and this code trusted.
    generated_sql: Mapped[str | None] = mapped_column(Text, nullable=True)
    intent: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # "answered" (query executed, rows below), "unsupported" (couldn't map
    # the question to a known analytical pattern - see app/analytics/
    # nl_parser.py), "error" (parsed fine but execution failed).
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    columns: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    rows: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)

    # One-directional only (no back_populates on Dataset) - same convention
    # already used for every other dataset_id-FK'd child table in this
    # codebase (MLRun, ModelVersion): the DB-level ondelete=CASCADE above
    # handles cleanup, so Dataset itself doesn't need to know about its
    # analytics query history. Kept here purely for convenient
    # `query.dataset.name` access when building API responses.
    dataset: Mapped["Dataset"] = relationship()
