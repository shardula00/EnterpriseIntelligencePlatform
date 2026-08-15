"""Pydantic request/response models for the analytics API (app/api/analytics.py)."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

AnalyticsQueryStatus = Literal["answered", "unsupported", "error"]


class AnalyticsQueryRequest(BaseModel):
    dataset_id: UUID
    question: str = Field(min_length=1, max_length=500)


class AnalyticsQueryOut(BaseModel):
    id: UUID
    dataset_id: UUID
    dataset_name: str
    question: str
    status: AnalyticsQueryStatus
    generated_sql: str | None
    intent: str | None
    error_message: str | None
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    created_at: datetime


class AnalyticsQuerySummaryOut(BaseModel):
    id: UUID
    dataset_id: UUID
    dataset_name: str
    question: str
    status: AnalyticsQueryStatus
    row_count: int
    created_at: datetime
