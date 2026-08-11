"""Pydantic request/response models for the ML API.

Pure data shapes, no logic - matches the convention already used in
app/bi/schemas.py and app/audit/schemas.py. Actual computation lives in
the per-task modules and service.py.
"""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

TaskType = Literal["classification", "forecasting", "segmentation", "anomaly_detection"]

# ---------------------------------------------------------------------------
# Suitability
# ---------------------------------------------------------------------------


class TaskSuitabilityOut(BaseModel):
    task_type: TaskType
    suitable: bool
    reasons: list[str]
    suggested_target_columns: list[str] = Field(default_factory=list)
    suggested_datetime_columns: list[str] = Field(default_factory=list)
    suggested_feature_columns: list[str] = Field(default_factory=list)


class DatasetSuitabilityOut(BaseModel):
    dataset_id: UUID
    row_count: int
    tasks: list[TaskSuitabilityOut]


# ---------------------------------------------------------------------------
# Train requests
# ---------------------------------------------------------------------------


class ClassificationTrainRequest(BaseModel):
    dataset_id: UUID
    target_column: str
    feature_columns: list[str] | None = None
    test_size: float = Field(default=0.25, gt=0.0, lt=0.9)
    random_seed: int | None = None


class ForecastTrainRequest(BaseModel):
    dataset_id: UUID
    datetime_column: str
    target_column: str
    horizon: int = Field(default=14, ge=1, le=180)
    random_seed: int | None = None


class SegmentationTrainRequest(BaseModel):
    dataset_id: UUID
    feature_columns: list[str] | None = None
    n_clusters: int = Field(default=4, ge=2, le=8)
    random_seed: int | None = None


class AnomalyTrainRequest(BaseModel):
    dataset_id: UUID
    feature_columns: list[str] | None = None
    contamination: float = Field(default=0.05, gt=0.0, le=0.5)
    random_seed: int | None = None


class PredictRequest(BaseModel):
    # Only meaningful for a forecasting run (request a different horizon
    # than the one used at training time); ignored by other task types.
    horizon: int | None = Field(default=None, ge=1, le=180)


# ---------------------------------------------------------------------------
# Shared pieces
# ---------------------------------------------------------------------------


class CandidateModelMetrics(BaseModel):
    model_name: str
    metrics: dict[str, float]


class FeatureImportanceOut(BaseModel):
    feature: str
    importance: float
    # "positive"/"negative" only when technically defensible (a linear
    # model's coefficient sign) - never implies causation. See
    # app/ml/explainability.py.
    direction: str | None = None


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


class ConfusionMatrixOut(BaseModel):
    labels: list[str]
    matrix: list[list[int]]


class ClassificationSamplePrediction(BaseModel):
    row_index: int
    actual: str
    predicted: str
    probability: float


class ClassificationResultsOut(BaseModel):
    target_column: str
    feature_columns: list[str]
    class_distribution: dict[str, int]
    candidate_models: list[CandidateModelMetrics]
    selected_model: str
    primary_metric: str
    primary_metric_rationale: str
    metrics: dict[str, float]
    confusion_matrix: ConfusionMatrixOut
    feature_importance: list[FeatureImportanceOut]
    sample_predictions: list[ClassificationSamplePrediction]
    test_size: float
    random_seed: int
    was_sampled: bool


# ---------------------------------------------------------------------------
# Forecasting
# ---------------------------------------------------------------------------


class TimeSeriesPointOut(BaseModel):
    period: str
    value: float


class ForecastPointOut(BaseModel):
    period: str
    value: float
    lower: float | None = None
    upper: float | None = None


class ForecastResultsOut(BaseModel):
    datetime_column: str
    target_column: str
    horizon: int
    candidate_models: list[CandidateModelMetrics]
    selected_model: str
    primary_metric: str
    metrics: dict[str, float]
    historical: list[TimeSeriesPointOut]
    forecast: list[ForecastPointOut]
    has_confidence_interval: bool
    random_seed: int


# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------


class ClusterProfileOut(BaseModel):
    cluster: int
    size: int
    feature_means: dict[str, float]


class SegmentationResultsOut(BaseModel):
    feature_columns: list[str]
    n_clusters: int
    silhouette_score: float
    cluster_sizes: dict[str, int]
    cluster_profiles: list[ClusterProfileOut]
    cluster_centers: list[list[float]]
    random_seed: int
    was_sampled: bool


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------


class AnomalyRecordOut(BaseModel):
    row_index: int
    anomaly_score: float
    is_anomaly: bool
    values: dict[str, Any]


class AnomalyResultsOut(BaseModel):
    feature_columns: list[str]
    contamination: float
    anomaly_count: int
    anomaly_percentage: float
    anomalous_records: list[AnomalyRecordOut]
    score_summary: dict[str, float]
    random_seed: int
    was_sampled: bool


# ---------------------------------------------------------------------------
# Per-row prediction shapes - one per task, see predict_*() in each task
# module. Kept distinct (rather than one dict[str, Any]) so /ml/runs/{id}/
# predict's response is fully typed too, not just training results.
# ---------------------------------------------------------------------------


class ClassificationPredictionOut(BaseModel):
    row_index: int
    predicted: str
    probability: float


class SegmentationPredictionOut(BaseModel):
    row_index: int
    cluster: int


class AnomalyPredictionOut(BaseModel):
    row_index: int
    anomaly_score: float
    is_anomaly: bool


# ---------------------------------------------------------------------------
# Run metadata + predict
# ---------------------------------------------------------------------------


class MLRunOut(BaseModel):
    id: UUID
    dataset_id: UUID
    task_type: TaskType
    model_name: str
    status: str
    configuration: dict[str, Any]
    created_by: UUID | None
    created_at: datetime
    completed_at: datetime | None


class MLRunResultsOut(BaseModel):
    run: MLRunOut
    # A real union, not dict[str, Any]: MLRun.results is stored as a plain
    # JSONB dict (its shape genuinely differs per task, so a single
    # database column can't be one Pydantic type) - but re-validating it
    # against this union on the way out means the OpenAPI schema (and so
    # the generated frontend types) describes all 4 real result shapes
    # instead of an opaque blob. Pydantic v2's "smart" union mode picks the
    # matching member by which one actually validates - safe here because
    # the 4 shapes have non-overlapping required fields (e.g. only
    # ClassificationResultsOut has `confusion_matrix`).
    results: (
        ClassificationResultsOut | ForecastResultsOut | SegmentationResultsOut | AnomalyResultsOut
    )


class PredictionResponseOut(BaseModel):
    run_id: UUID
    task_type: TaskType
    predictions: (
        list[ClassificationPredictionOut]
        | list[SegmentationPredictionOut]
        | list[AnomalyPredictionOut]
        | list[ForecastPointOut]
    )
    summary: dict[str, Any]
