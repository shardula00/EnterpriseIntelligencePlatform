"""Pydantic response models for the KPI API."""

from uuid import UUID

from pydantic import BaseModel


class KpiValueOut(BaseModel):
    column: str
    kind: str
    value: float | None


class KpiSummaryOut(BaseModel):
    dataset_id: UUID
    kpis: list[KpiValueOut]
    numeric_columns: list[str]
    suggested_breakdown_columns: list[str]
    suggested_trend_columns: list[str]


class BreakdownItemOut(BaseModel):
    category: str
    value: float


class BreakdownOut(BaseModel):
    dataset_id: UUID
    group_by: str
    metric: str | None
    aggregation: str
    items: list[BreakdownItemOut]
    total_categories: int


class TrendPointOut(BaseModel):
    period: str
    value: float


class TrendOut(BaseModel):
    dataset_id: UUID
    date_column: str
    metric: str
    granularity: str
    aggregation: str
    points: list[TrendPointOut]
