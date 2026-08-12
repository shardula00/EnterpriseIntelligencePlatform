"""Orchestration layer for the MLOps API - the only module app/api/mlops.py
calls, mirroring app/ml/service.py's role for the training API.

Ties together: app.ml.service (run/artifact lookup - never re-implemented
here), registry_service (lifecycle), drift.py/monitoring.py (the actual
statistics), and MonitoringEvent persistence.
"""

import uuid
from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.ingestion.service import get_dataset
from app.ml import service as ml_service
from app.ml.artifacts import load_artifact
from app.ml.data_loading import downsample_if_needed, load_dataset_dataframe
from app.ml.schemas import MLRunOut, MLRunResultsOut
from app.mlops import monitoring, registry_service
from app.mlops.drift import compute_drift
from app.mlops.errors import InsufficientDataForMonitoringError
from app.models.dataset import Dataset
from app.models.ml_run import MLRun
from app.models.model_version import ModelVersion
from app.models.monitoring_event import MonitoringEvent

_CHECKERS = {
    "classification": monitoring.check_classification_performance,
    "forecasting": monitoring.check_forecast_performance,
    "segmentation": monitoring.check_segmentation_performance,
    "anomaly_detection": monitoring.check_anomaly_performance,
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _to_run_results_out(run: MLRun) -> MLRunResultsOut:
    run_out = MLRunOut.model_validate(run, from_attributes=True)
    return MLRunResultsOut(run=run_out, results=run.results)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def register_model_version(
    db: Session, settings: Settings, ml_run_id: uuid.UUID, created_by: uuid.UUID | None
) -> ModelVersion:
    run = ml_service.get_run(db, ml_run_id)
    return registry_service.register_version(db, settings, run, created_by)


def get_model_version_detail(
    db: Session, version_id: uuid.UUID
) -> tuple[ModelVersion, MLRunResultsOut]:
    version = registry_service.get_version(db, version_id)
    run = ml_service.get_run(db, version.ml_run_id)
    return version, _to_run_results_out(run)


def list_model_versions(
    db: Session, *, dataset_id: uuid.UUID | None, task_type: str | None, status: str | None
) -> list[ModelVersion]:
    return registry_service.list_versions(
        db, dataset_id=dataset_id, task_type=task_type, status=status
    )


def promote_model_version(
    db: Session, version_id: uuid.UUID, target_status: str, promoted_by: uuid.UUID | None
) -> tuple[ModelVersion, ModelVersion | None]:
    version = registry_service.get_version(db, version_id)
    run = ml_service.get_run(db, version.ml_run_id)
    return registry_service.promote_version(db, version_id, target_status, promoted_by, run)


def archive_model_version(
    db: Session, version_id: uuid.UUID, archived_by: uuid.UUID | None
) -> ModelVersion:
    return registry_service.archive_version(db, version_id, archived_by)


# ---------------------------------------------------------------------------
# Shared helpers for drift/monitoring
# ---------------------------------------------------------------------------


def _column_types(dataset: Dataset) -> dict[str, str]:
    return {
        c.column_name: ("numeric" if c.detected_type in {"integer", "float"} else "categorical")
        for c in dataset.columns
    }


def _drift_feature_columns(run: MLRun) -> list[str]:
    if run.task_type == "forecasting":
        # Forecasting has no user-selected feature_columns (see
        # app/ml/forecasting.py) - the target's own distribution is what a
        # drift check on a time series actually means here.
        return [run.configuration["target_column"]]
    return run.configuration["feature_columns"]


def _severity_for_drift(overall_status: str) -> str:
    mapping = {"drift": "critical", "warning": "warning", "stable": "info", "unknown": "info"}
    return mapping[overall_status]


def _severity_for_performance(status: str) -> str:
    mapping = {
        "degraded": "critical", "warning": "warning", "stable": "info", "not_applicable": "info",
    }
    return mapping[status]


# ---------------------------------------------------------------------------
# Drift
# ---------------------------------------------------------------------------


def run_drift_check(
    db: Session, settings: Settings, version_id: uuid.UUID, dataset_id: uuid.UUID,
    created_by: uuid.UUID | None,
) -> tuple[dict, MonitoringEvent]:
    version = registry_service.get_version(db, version_id)
    run = ml_service.get_run(db, version.ml_run_id)
    baseline_dataset = get_dataset(db, run.dataset_id)
    current_dataset = get_dataset(db, dataset_id)

    baseline_df = load_dataset_dataframe(db, baseline_dataset)
    current_df = load_dataset_dataframe(db, current_dataset)

    feature_columns = _drift_feature_columns(run)
    column_types = _column_types(baseline_dataset)
    result = compute_drift(baseline_df, current_df, feature_columns, column_types, settings)

    explanation = (
        f"{result.drifted_feature_count} of {result.total_features_checked} feature(s) show "
        f"significant drift, {result.warning_feature_count} show moderate drift, comparing "
        f"'{current_dataset.name}' against the model's original training data "
        f"('{baseline_dataset.name}')."
    )
    payload = {
        "model_version_id": str(version_id),
        "dataset_id": str(dataset_id),
        "overall_status": result.overall_status,
        "total_features_checked": result.total_features_checked,
        "drifted_feature_count": result.drifted_feature_count,
        "warning_feature_count": result.warning_feature_count,
        "warning_threshold": settings.drift_psi_warning_threshold,
        "severe_threshold": settings.drift_psi_severe_threshold,
        "features": [asdict(f) for f in result.features],
        "explanation": explanation,
    }

    event = MonitoringEvent(
        model_version_id=version_id,
        dataset_id=dataset_id,
        event_type="drift",
        severity=_severity_for_drift(result.overall_status),
        summary=f"Drift check: {result.overall_status} against '{current_dataset.name}'.",
        details=payload,
        created_by=created_by,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return payload, event


# ---------------------------------------------------------------------------
# Performance monitoring
# ---------------------------------------------------------------------------


def run_performance_check(
    db: Session, settings: Settings, version_id: uuid.UUID, dataset_id: uuid.UUID,
    created_by: uuid.UUID | None,
) -> tuple[dict, MonitoringEvent]:
    version = registry_service.get_version(db, version_id)
    run = ml_service.get_run(db, version.ml_run_id)
    checker = _CHECKERS.get(run.task_type)
    if checker is None:  # pragma: no cover - task_type is constrained at write time
        raise InsufficientDataForMonitoringError(f"Unknown task type '{run.task_type}'.")

    artifact = load_artifact(settings.ml_artifacts_dir, run.id)
    dataset = get_dataset(db, dataset_id)
    df = load_dataset_dataframe(db, dataset)
    if run.task_type != "forecasting":
        df, _ = downsample_if_needed(
            df, settings.ml_max_training_rows, settings.ml_default_random_seed
        )

    result = checker(artifact, df, run, settings)

    payload = {
        "model_version_id": str(version_id),
        "dataset_id": str(dataset_id),
        "task_type": run.task_type,
        "ground_truth_available": result.ground_truth_available,
        "primary_metric": result.primary_metric,
        "baseline_value": result.baseline_value,
        "current_value": result.current_value,
        "absolute_change": result.absolute_change,
        "relative_change": result.relative_change,
        "warning_threshold": settings.performance_degradation_warning_threshold,
        "severe_threshold": settings.performance_degradation_severe_threshold,
        "status": result.status,
        "explanation": result.explanation,
        "extra_metrics": result.extra_metrics,
    }

    event = MonitoringEvent(
        model_version_id=version_id,
        dataset_id=dataset_id,
        event_type="performance_monitoring",
        severity=_severity_for_performance(result.status),
        summary=f"Performance check: {result.status} against '{dataset.name}'.",
        details=payload,
        created_by=created_by,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return payload, event


# ---------------------------------------------------------------------------
# Monitoring events / alerts
# ---------------------------------------------------------------------------


def list_monitoring_events(
    db: Session, *, model_version_id: uuid.UUID | None = None, event_type: str | None = None,
    severity: str | None = None, limit: int = 100,
) -> list[MonitoringEvent]:
    stmt = select(MonitoringEvent).order_by(MonitoringEvent.created_at.desc()).limit(limit)
    if model_version_id is not None:
        stmt = stmt.where(MonitoringEvent.model_version_id == model_version_id)
    if event_type is not None:
        stmt = stmt.where(MonitoringEvent.event_type == event_type)
    if severity is not None:
        stmt = stmt.where(MonitoringEvent.severity == severity)
    return list(db.execute(stmt).scalars())
