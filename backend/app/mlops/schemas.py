"""Pydantic request/response models for the MLOps API.

Reuses app.ml.schemas.MLRunResultsOut for a version's training
config/metrics rather than re-declaring those fields - see
app/models/model_version.py's docstring for why a ModelVersion never
duplicates that data.
"""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.ml.schemas import MLRunResultsOut, TaskType

LifecycleStatus = Literal["candidate", "staging", "production", "archived"]
DriftStatus = Literal["stable", "warning", "drift", "unknown"]
PerformanceStatus = Literal["stable", "warning", "degraded", "not_applicable"]
Severity = Literal["info", "warning", "critical"]

# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------


class ModelVersionOut(BaseModel):
    id: UUID
    ml_run_id: UUID
    dataset_id: UUID
    task_type: TaskType
    model_name: str
    version_number: int
    status: LifecycleStatus
    artifact_checksum: str
    created_by: UUID | None
    created_at: datetime
    promoted_by: UUID | None
    promoted_at: datetime | None


class ModelVersionDetailOut(BaseModel):
    version: ModelVersionOut
    run: MLRunResultsOut


class RegisterModelVersionRequest(BaseModel):
    ml_run_id: UUID


class PromoteModelVersionRequest(BaseModel):
    target_status: Literal["staging", "production"]


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------


class DriftCheckRequest(BaseModel):
    dataset_id: UUID


class FeatureDriftOut(BaseModel):
    feature: str
    feature_type: Literal["numeric", "categorical"]
    method: Literal["psi", "constant_value_deviation", "insufficient_data"]
    statistic: float | None
    status: DriftStatus
    baseline_summary: dict[str, Any]
    current_summary: dict[str, Any]
    explanation: str


class DriftResultOut(BaseModel):
    model_version_id: UUID
    dataset_id: UUID
    overall_status: DriftStatus
    total_features_checked: int
    drifted_feature_count: int
    warning_feature_count: int
    warning_threshold: float
    severe_threshold: float
    features: list[FeatureDriftOut]
    explanation: str


# ---------------------------------------------------------------------------
# Performance monitoring
# ---------------------------------------------------------------------------


class PerformanceCheckRequest(BaseModel):
    dataset_id: UUID


class PerformanceCheckOut(BaseModel):
    model_version_id: UUID
    dataset_id: UUID
    task_type: TaskType
    ground_truth_available: bool
    primary_metric: str | None
    baseline_value: float | None
    current_value: float | None
    absolute_change: float | None
    relative_change: float | None
    warning_threshold: float
    severe_threshold: float
    status: PerformanceStatus
    explanation: str
    # Secondary metrics recomputed for context, not used for the status
    # decision itself (only primary_metric drives status).
    extra_metrics: dict[str, float] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Monitoring events / alerts
# ---------------------------------------------------------------------------


class MonitoringEventOut(BaseModel):
    id: UUID
    model_version_id: UUID
    dataset_id: UUID
    event_type: Literal["drift", "performance_monitoring"]
    severity: Severity
    summary: str
    details: dict[str, Any]
    created_by: UUID | None
    created_at: datetime
