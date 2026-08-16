"""Pydantic request/response models for the decisions API (app/api/decisions.py)."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

Confidence = Literal["low", "medium", "high"]
RecommendationStatus = Literal["pending", "approved", "rejected"]


class RecommendationRequest(BaseModel):
    dataset_id: UUID
    question: str = Field(min_length=1, max_length=500)


class ScenarioRequest(BaseModel):
    dataset_id: UUID
    question: str = Field(min_length=1, max_length=500)


class ScenarioResultOut(BaseModel):
    computed: bool
    question: str
    affected_metric: str | None = None
    perturbed_metric: str | None = None
    delta_percent: float | None = None
    baseline_perturbed_value: float | None = None
    baseline_affected_value: float | None = None
    new_perturbed_value: float | None = None
    new_affected_value: float | None = None
    affected_value_change: float | None = None
    relationship: str | None = None
    note: str | None = None
    reason: str | None = None


class RecommendationOut(BaseModel):
    id: UUID
    dataset_id: UUID
    question: str
    recommendation: str
    alternatives: list[str]
    evidence: list[dict[str, Any]]
    risks: list[dict[str, Any]]
    assumptions: list[str]
    confidence: Confidence
    expected_impact: dict[str, Any] | None
    status: RecommendationStatus
    decided_by: UUID | None
    decided_at: datetime | None
    created_at: datetime


class RecommendationSummaryOut(BaseModel):
    id: UUID
    dataset_id: UUID
    question: str
    recommendation: str
    confidence: Confidence
    status: RecommendationStatus
    created_at: datetime
