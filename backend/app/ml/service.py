"""Orchestration layer for the ML API.

app/api/ml.py talks only to this module - never directly to suitability.py,
the task modules, or artifacts.py. The flow every train_*_run() follows is
identical:

    1. look up the dataset (reusing app.ingestion.service, not a second
       lookup path)
    2. validate the specific request against that dataset's columns
       (app.ml.suitability.validate_*_request) - raises
       InvalidMlConfigurationError with a specific reason on failure
    3. load the dataset's full table into a DataFrame (app.ml.data_loading),
       downsampling if it exceeds Settings.ml_max_training_rows
    4. hand off to the task module's train_*() function, which does the
       actual leakage-safe fit/evaluate/select
    5. persist an MLRun row (metadata + full results) and the fitted
       artifact (app.ml.artifacts), and return both together

Training is synchronous end-to-end - see app/ml/__init__.py for why that's
an acceptable, documented limitation for this phase rather than something
silently swept under the rug.
"""

import uuid
from datetime import UTC, datetime

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.ingestion.service import get_dataset
from app.ml import suitability
from app.ml.anomaly_detection import AnomalyArtifact, predict_anomaly, train_anomaly
from app.ml.artifacts import load_artifact, save_artifact
from app.ml.classification import (
    ClassificationArtifact,
    predict_classification,
    train_classification,
)
from app.ml.data_loading import downsample_if_needed, load_dataset_dataframe
from app.ml.errors import MlRunNotFoundError
from app.ml.evaluation import resolve_seed
from app.ml.forecasting import ForecastArtifact, predict_forecast, train_forecast
from app.ml.schemas import (
    AnomalyTrainRequest,
    ClassificationTrainRequest,
    DatasetSuitabilityOut,
    ForecastTrainRequest,
    PredictionResponseOut,
    SegmentationTrainRequest,
    TaskSuitabilityOut,
)
from app.ml.segmentation import SegmentationArtifact, predict_segmentation, train_segmentation
from app.models.ml_run import MLRun


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _downsample(df: pd.DataFrame, settings: Settings) -> tuple[pd.DataFrame, bool]:
    """Shared by the 3 row-order-independent tasks (classification,
    segmentation, anomaly detection) - never called for forecasting, where
    row order is the signal (see train_forecast_run)."""
    return downsample_if_needed(df, settings.ml_max_training_rows, settings.ml_default_random_seed)


# ---------------------------------------------------------------------------
# Suitability
# ---------------------------------------------------------------------------


def get_dataset_suitability(db: Session, dataset_id: uuid.UUID) -> DatasetSuitabilityOut:
    dataset = get_dataset(db, dataset_id)
    checks = suitability.check_all_tasks(dataset, dataset.columns)
    return DatasetSuitabilityOut(
        dataset_id=dataset.id,
        row_count=dataset.row_count,
        tasks=[
            TaskSuitabilityOut(
                task_type=task_type,
                suitable=check.suitable,
                reasons=check.reasons,
                suggested_target_columns=check.suggested_target_columns,
                suggested_datetime_columns=check.suggested_datetime_columns,
                suggested_feature_columns=check.suggested_feature_columns,
            )
            for task_type, check in checks.items()
        ],
    )


# ---------------------------------------------------------------------------
# Persistence helper - shared by all four train_*_run() functions
# ---------------------------------------------------------------------------


def _persist_run(
    db: Session,
    settings: Settings,
    *,
    dataset_id: uuid.UUID,
    task_type: str,
    model_name: str,
    configuration: dict,
    results: dict,
    artifact: object,
    created_by: uuid.UUID | None,
) -> MLRun:
    run = MLRun(
        dataset_id=dataset_id,
        task_type=task_type,
        model_name=model_name,
        configuration=configuration,
        results=results,
        created_by=created_by,
        completed_at=_utcnow(),
    )
    db.add(run)
    db.flush()  # assigns run.id without ending the transaction

    path = save_artifact(settings.ml_artifacts_dir, run.id, artifact)
    run.artifact_path = str(path)

    db.commit()
    db.refresh(run)
    return run


# ---------------------------------------------------------------------------
# Train
# ---------------------------------------------------------------------------


def train_classification_run(
    db: Session,
    settings: Settings,
    request: ClassificationTrainRequest,
    created_by: uuid.UUID | None,
) -> MLRun:
    dataset = get_dataset(db, request.dataset_id)
    feature_columns = suitability.validate_classification_request(
        dataset.columns, request.target_column, request.feature_columns
    )

    df = load_dataset_dataframe(db, dataset)
    df, was_sampled = _downsample(df, settings)
    seed = resolve_seed(request.random_seed, settings)

    results, artifact = train_classification(
        df,
        dataset.columns,
        target_column=request.target_column,
        feature_columns=feature_columns,
        test_size=request.test_size,
        random_seed=seed,
    )
    results.was_sampled = was_sampled

    return _persist_run(
        db,
        settings,
        dataset_id=dataset.id,
        task_type="classification",
        model_name=results.selected_model,
        configuration={
            "target_column": request.target_column,
            "feature_columns": feature_columns,
            "test_size": request.test_size,
            "random_seed": seed,
            "was_sampled": was_sampled,
        },
        results=results.model_dump(),
        artifact=artifact,
        created_by=created_by,
    )


def train_forecast_run(
    db: Session, settings: Settings, request: ForecastTrainRequest, created_by: uuid.UUID | None
) -> MLRun:
    dataset = get_dataset(db, request.dataset_id)
    suitability.validate_forecast_request(
        dataset.columns, request.datetime_column, request.target_column
    )

    # Never downsampled: forecasting's row ORDER is the signal, and a random
    # sample would destroy the chronological sequence lags/backtests depend
    # on. ml_max_training_rows is a training-cost guard for the other three
    # tasks; a time series this large is not something Phase 5 targets.
    df = load_dataset_dataframe(db, dataset)
    seed = resolve_seed(request.random_seed, settings)

    results, artifact = train_forecast(
        df,
        datetime_column=request.datetime_column,
        target_column=request.target_column,
        horizon=request.horizon,
        random_seed=seed,
    )

    return _persist_run(
        db,
        settings,
        dataset_id=dataset.id,
        task_type="forecasting",
        model_name=results.selected_model,
        configuration={
            "datetime_column": request.datetime_column,
            "target_column": request.target_column,
            "horizon": request.horizon,
            "random_seed": seed,
        },
        results=results.model_dump(),
        artifact=artifact,
        created_by=created_by,
    )


def train_segmentation_run(
    db: Session,
    settings: Settings,
    request: SegmentationTrainRequest,
    created_by: uuid.UUID | None,
) -> MLRun:
    dataset = get_dataset(db, request.dataset_id)
    feature_columns = suitability.validate_segmentation_request(
        dataset.columns, request.feature_columns
    )

    df = load_dataset_dataframe(db, dataset)
    df, was_sampled = _downsample(df, settings)
    seed = resolve_seed(request.random_seed, settings)

    results, artifact = train_segmentation(
        df, feature_columns=feature_columns, n_clusters=request.n_clusters, random_seed=seed
    )
    results.was_sampled = was_sampled

    return _persist_run(
        db,
        settings,
        dataset_id=dataset.id,
        task_type="segmentation",
        model_name="K-Means",
        configuration={
            "feature_columns": feature_columns,
            "n_clusters": request.n_clusters,
            "random_seed": seed,
            "was_sampled": was_sampled,
        },
        results=results.model_dump(),
        artifact=artifact,
        created_by=created_by,
    )


def train_anomaly_run(
    db: Session, settings: Settings, request: AnomalyTrainRequest, created_by: uuid.UUID | None
) -> MLRun:
    dataset = get_dataset(db, request.dataset_id)
    feature_columns = suitability.validate_anomaly_request(
        dataset.columns, request.feature_columns
    )

    df = load_dataset_dataframe(db, dataset)
    df, was_sampled = _downsample(df, settings)
    seed = resolve_seed(request.random_seed, settings)

    results, artifact = train_anomaly(
        df, feature_columns=feature_columns, contamination=request.contamination, random_seed=seed
    )
    results.was_sampled = was_sampled

    return _persist_run(
        db,
        settings,
        dataset_id=dataset.id,
        task_type="anomaly_detection",
        model_name="Isolation Forest",
        configuration={
            "feature_columns": feature_columns,
            "contamination": request.contamination,
            "random_seed": seed,
            "was_sampled": was_sampled,
        },
        results=results.model_dump(),
        artifact=artifact,
        created_by=created_by,
    )


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def get_run(db: Session, run_id: uuid.UUID) -> MLRun:
    run = db.get(MLRun, run_id)
    if run is None:
        raise MlRunNotFoundError(f"ML run {run_id} not found.")
    return run


def list_runs(
    db: Session,
    *,
    dataset_id: uuid.UUID | None = None,
    task_type: str | None = None,
    limit: int = 50,
) -> list[MLRun]:
    stmt = select(MLRun).order_by(MLRun.created_at.desc()).limit(limit)
    if dataset_id is not None:
        stmt = stmt.where(MLRun.dataset_id == dataset_id)
    if task_type is not None:
        stmt = stmt.where(MLRun.task_type == task_type)
    return list(db.execute(stmt).scalars())


# ---------------------------------------------------------------------------
# Predict - reloads the persisted artifact, never retrains
# ---------------------------------------------------------------------------


def predict_run(
    db: Session, settings: Settings, run_id: uuid.UUID, horizon: int | None
) -> PredictionResponseOut:
    run = get_run(db, run_id)
    artifact = load_artifact(settings.ml_artifacts_dir, run.id)
    dataset = get_dataset(db, run.dataset_id)

    if run.task_type == "forecasting":
        assert isinstance(artifact, ForecastArtifact)
        effective_horizon = horizon if horizon is not None else run.configuration["horizon"]
        points = predict_forecast(artifact, effective_horizon)
        predictions = [p.model_dump() for p in points]
        summary = {"horizon": effective_horizon, "model": run.model_name}
        return PredictionResponseOut(
            run_id=run.id, task_type=run.task_type, predictions=predictions, summary=summary
        )

    df = load_dataset_dataframe(db, dataset)
    df, was_sampled = _downsample(df, settings)

    if run.task_type == "classification":
        assert isinstance(artifact, ClassificationArtifact)
        predictions = predict_classification(artifact, df)
        positive = artifact.label_names[1]
        summary = {
            "row_count": len(predictions),
            "predicted_positive": sum(1 for p in predictions if p["predicted"] == positive),
            "was_sampled": was_sampled,
        }
    elif run.task_type == "segmentation":
        assert isinstance(artifact, SegmentationArtifact)
        predictions = predict_segmentation(artifact, df)
        summary = {"row_count": len(predictions), "was_sampled": was_sampled}
    elif run.task_type == "anomaly_detection":
        assert isinstance(artifact, AnomalyArtifact)
        predictions = predict_anomaly(artifact, df)
        summary = {
            "row_count": len(predictions),
            "anomaly_count": sum(1 for p in predictions if p["is_anomaly"]),
            "was_sampled": was_sampled,
        }
    else:  # pragma: no cover - task_type is constrained at write time
        raise MlRunNotFoundError(f"Unknown task type '{run.task_type}' on run {run_id}.")

    return PredictionResponseOut(
        run_id=run.id, task_type=run.task_type, predictions=predictions, summary=summary
    )
