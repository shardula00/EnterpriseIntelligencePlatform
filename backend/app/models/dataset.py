"""Ingestion metadata models (Phase 2).

These four tables describe *any* uploaded dataset generically - nothing
here names a specific business schema. The actual uploaded data lives in a
separate, dynamically created table per dataset (see
app/ingestion/table_builder.py), in the `ingested` Postgres schema; these
tables (in the default `public` schema) only ever store facts *about* that
data: what it looked like, how it scored, and what happened to it.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)

    storage_schema: Mapped[str] = mapped_column(String(63), nullable=False)
    storage_table_name: Mapped[str] = mapped_column(String(63), nullable=False, unique=True)

    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ready")

    # Path to the retained raw upload, relative to Settings.upload_storage_dir.
    # NULL if the raw file couldn't be retained for some reason.
    source_file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)

    columns: Mapped[list["DatasetColumn"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan", order_by="DatasetColumn.position"
    )
    quality_issues: Mapped[list["DatasetQualityIssue"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )
    lineage_events: Mapped[list["DatasetLineageEvent"]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="DatasetLineageEvent.created_at",
    )


class DatasetColumn(Base):
    __tablename__ = "dataset_columns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    column_name: Mapped[str] = mapped_column(String(63), nullable=False)
    detected_type: Mapped[str] = mapped_column(String(20), nullable=False)
    nullable: Mapped[bool] = mapped_column(default=True, nullable=False)

    null_count: Mapped[int] = mapped_column(Integer, nullable=False)
    distinct_count: Mapped[int] = mapped_column(Integer, nullable=False)
    min_value: Mapped[str | None] = mapped_column(String(200), nullable=True)
    max_value: Mapped[str | None] = mapped_column(String(200), nullable=True)
    mean_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_values: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    dataset: Mapped["Dataset"] = relationship(back_populates="columns")


class DatasetQualityIssue(Base):
    __tablename__ = "dataset_quality_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )

    rule: Mapped[str] = mapped_column(String(50), nullable=False)
    column_name: Mapped[str | None] = mapped_column(String(63), nullable=True)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    score_impact: Mapped[float] = mapped_column(Float, nullable=False)

    dataset: Mapped["Dataset"] = relationship(back_populates="quality_issues")


class DatasetLineageEvent(Base):
    __tablename__ = "dataset_lineage_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )

    step: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)

    dataset: Mapped["Dataset"] = relationship(back_populates="lineage_events")
