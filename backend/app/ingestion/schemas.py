"""Pydantic response models for the ingestion API.

Where a schema maps 1:1 onto an ORM model (ColumnInfo <-> DatasetColumn,
etc.) it uses `from_attributes=True` so the router can build the response
directly via `Model.model_validate(orm_instance)`.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ColumnInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    position: int
    original_name: str
    column_name: str
    detected_type: str
    nullable: bool
    null_count: int
    distinct_count: int
    min_value: str | None
    max_value: str | None
    mean_value: float | None
    sample_values: list[Any] | None


class QualityIssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rule: str
    column_name: str | None
    severity: str
    message: str
    score_impact: float


class LineageEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    step: str
    status: str
    detail: dict[str, Any] | None
    created_at: datetime


class DatasetSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    original_filename: str
    file_type: str
    storage_schema: str
    storage_table_name: str
    row_count: int
    column_count: int
    quality_score: float
    status: str
    created_at: datetime


class DatasetDetail(DatasetSummary):
    columns: list[ColumnInfo]


class QualityReportOut(BaseModel):
    dataset_id: UUID
    quality_score: float
    issues: list[QualityIssueOut]


class LineageOut(BaseModel):
    dataset_id: UUID
    events: list[LineageEventOut]


class PreviewOut(BaseModel):
    dataset_id: UUID
    columns: list[str]
    rows: list[dict[str, Any]]
