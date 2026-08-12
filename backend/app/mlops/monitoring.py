"""Model performance monitoring: compare a model version's recorded
training-time metric against the same metric recomputed on a new dataset.

Only meaningful when genuine ground truth is available - a known-correct
target column (classification) or known-actual future values
(forecasting). Segmentation and anomaly detection have no such thing by
construction (see app/ml/segmentation.py and anomaly_detection.py's own
docstrings), so their checks report `ground_truth_available=False` and
compare an unsupervised proxy signal instead (silhouette score;
anomaly rate) - never dressed up as a true accuracy measurement. This
module never retrains or changes anything; it only ever reports a status.

Status thresholds compare the *relative* change in the primary metric
against Settings.performance_degradation_{warning,severe}_threshold,
direction-aware: for a "higher is better" metric (ROC-AUC, silhouette) a
drop is degradation; for a "lower is better" metric (MAE) a rise is.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    precision_score,
    recall_score,
    roc_auc_score,
    silhouette_score,
)

from app.config import Settings
from app.ml.anomaly_detection import AnomalyArtifact
from app.ml.classification import ClassificationArtifact
from app.ml.forecasting import ForecastArtifact, predict_forecast
from app.ml.segmentation import SegmentationArtifact
from app.mlops.errors import InsufficientDataForMonitoringError
from app.models.ml_run import MLRun


@dataclass
class PerformanceCheckResult:
    ground_truth_available: bool
    primary_metric: str | None
    baseline_value: float | None
    current_value: float | None
    absolute_change: float | None
    relative_change: float | None
    status: str  # "stable" | "warning" | "degraded" | "not_applicable"
    explanation: str
    extra_metrics: dict = field(default_factory=dict)


def _classify_change(
    baseline: float, current: float, higher_is_better: bool, warning: float, severe: float
) -> tuple[float, float | None, str]:
    absolute_change = round(current - baseline, 4)
    if baseline == 0:
        relative_change = None
    else:
        relative_change = round((current - baseline) / abs(baseline), 4)

    # The signed change that matters is "did the metric move in the *bad*
    # direction" - a ROC-AUC going up, or MAE going down, is never flagged.
    bad_direction_change = -absolute_change if higher_is_better else absolute_change
    magnitude = abs(relative_change) if relative_change is not None else abs(absolute_change)

    if bad_direction_change <= 0:
        status = "stable"
    elif magnitude >= severe:
        status = "degraded"
    elif magnitude >= warning:
        status = "warning"
    else:
        status = "stable"
    return absolute_change, relative_change, status


def check_classification_performance(
    artifact: ClassificationArtifact, df: pd.DataFrame, run: MLRun, settings: Settings
) -> PerformanceCheckResult:
    target_column = run.configuration["target_column"]
    if target_column not in df.columns:
        raise InsufficientDataForMonitoringError(
            f"Dataset does not contain the target column '{target_column}' required to "
            f"evaluate classification performance."
        )
    df = df.dropna(subset=[target_column])
    if df.empty:
        raise InsufficientDataForMonitoringError(
            f"No rows with a non-missing '{target_column}' value."
        )

    negative_label, positive_label = artifact.label_names
    y_true = (df[target_column].astype(str) == positive_label).astype(int)
    if y_true.nunique() < 2:
        # sklearn doesn't raise for this - it returns NaN with a warning,
        # which would otherwise silently produce a NaN "current_value".
        # Checked explicitly instead of relying on catching an exception
        # that this sklearn version doesn't actually throw.
        raise InsufficientDataForMonitoringError(
            f"Dataset's '{target_column}' column has only one class present - ROC-AUC "
            f"cannot be computed."
        )
    X = df[artifact.feature_columns]

    y_pred = artifact.pipeline.predict(X)
    y_proba = artifact.pipeline.predict_proba(X)[:, 1]

    baseline = run.results["metrics"]["roc_auc"]
    current = float(roc_auc_score(y_true, y_proba))

    absolute_change, relative_change, status = _classify_change(
        baseline, current, True,
        settings.performance_degradation_warning_threshold,
        settings.performance_degradation_severe_threshold,
    )
    extra = {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
    }
    return PerformanceCheckResult(
        True, "roc_auc", round(baseline, 4), round(current, 4), absolute_change, relative_change,
        status,
        _explain("roc_auc", baseline, current, status, settings),
        extra,
    )


def check_forecast_performance(
    artifact: ForecastArtifact, df: pd.DataFrame, run: MLRun, settings: Settings
) -> PerformanceCheckResult:
    datetime_column = run.configuration["datetime_column"]
    target_column = run.configuration["target_column"]
    if datetime_column not in df.columns or target_column not in df.columns:
        raise InsufficientDataForMonitoringError(
            f"Dataset must contain both '{datetime_column}' and '{target_column}' to evaluate "
            f"forecast performance against real actuals."
        )
    ts = df[[datetime_column, target_column]].dropna().copy()
    ts[datetime_column] = pd.to_datetime(ts[datetime_column])
    ts = ts.sort_values(datetime_column).reset_index(drop=True)
    if ts.empty:
        raise InsufficientDataForMonitoringError(
            "No non-missing actual values to evaluate against."
        )

    predictions = predict_forecast(artifact, horizon=len(ts))
    predicted_values = np.array([p.value for p in predictions[: len(ts)]])
    actual_values = ts[target_column].to_numpy(dtype=float)

    baseline = run.results["metrics"]["mae"]
    current = float(mean_absolute_error(actual_values, predicted_values))

    absolute_change, relative_change, status = _classify_change(
        baseline, current, False,
        settings.performance_degradation_warning_threshold,
        settings.performance_degradation_severe_threshold,
    )
    return PerformanceCheckResult(
        True, "mae", round(baseline, 4), round(current, 4), absolute_change, relative_change,
        status,
        _explain("mae", baseline, current, status, settings),
        {},
    )


def check_segmentation_performance(
    artifact: SegmentationArtifact, df: pd.DataFrame, run: MLRun, settings: Settings
) -> PerformanceCheckResult:
    X = df[artifact.feature_columns].dropna()
    if len(X) < 2:
        raise InsufficientDataForMonitoringError(
            "Not enough non-missing rows to compute silhouette score."
        )

    labels = artifact.pipeline.predict(X)
    if len(set(labels)) < 2:
        raise InsufficientDataForMonitoringError(
            "The model assigned every row in this dataset to the same cluster - silhouette "
            "score is undefined."
        )
    scaled_X = artifact.pipeline[:-1].transform(X)
    baseline = run.results["silhouette_score"]
    current = float(silhouette_score(scaled_X, labels))

    absolute_change, relative_change, status = _classify_change(
        baseline, current, True,
        settings.performance_degradation_warning_threshold,
        settings.performance_degradation_severe_threshold,
    )
    return PerformanceCheckResult(
        False, "silhouette_score", round(baseline, 4), round(current, 4),
        absolute_change, relative_change, status,
        "Segmentation has no ground truth - this compares silhouette score (an unsupervised "
        "cluster-quality signal), not a true accuracy measurement. "
        + _explain("silhouette_score", baseline, current, status, settings),
        {},
    )


def check_anomaly_performance(
    artifact: AnomalyArtifact, df: pd.DataFrame, run: MLRun, settings: Settings
) -> PerformanceCheckResult:
    X = df[artifact.feature_columns].dropna()
    if X.empty:
        raise InsufficientDataForMonitoringError(
            "Not enough non-missing rows to compute an anomaly rate."
        )

    is_anomaly = artifact.pipeline.predict(X) == -1
    baseline = run.results["anomaly_percentage"]
    current = round(100 * float(is_anomaly.mean()), 4)

    # Any rate shift is worth surfacing, in either direction - unlike a
    # supervised metric, there's no "good" direction for the anomaly rate to
    # move in, so both classify_change calls are checked and the worse one wins.
    _, relative_up, status_up = _classify_change(
        baseline, current, False,
        settings.performance_degradation_warning_threshold,
        settings.performance_degradation_severe_threshold,
    )
    _, relative_down, status_down = _classify_change(
        baseline, current, True,
        settings.performance_degradation_warning_threshold,
        settings.performance_degradation_severe_threshold,
    )
    status = "degraded" if "degraded" in (status_up, status_down) else (
        "warning" if "warning" in (status_up, status_down) else "stable"
    )
    absolute_change = round(current - baseline, 4)
    relative_change = relative_up if relative_up is not None else relative_down

    return PerformanceCheckResult(
        False, "anomaly_percentage", round(baseline, 4), current, absolute_change,
        relative_change, status,
        "Anomaly detection has no ground truth - this compares the flagged-anomaly rate "
        "against the training-time rate as a proxy signal, not a true accuracy measurement. "
        f"Baseline {round(baseline, 4)}% -> current {current}% "
        f"({'+' if absolute_change >= 0 else ''}{absolute_change} points).",
        {},
    )


def _explain(metric: str, baseline: float, current: float, status: str, settings: Settings) -> str:
    direction = "dropped" if current < baseline else "rose"
    return (
        f"{metric} {direction} from {round(baseline, 4)} (training) to {round(current, 4)} "
        f"(this check) - status '{status}' "
        f"(warning >= {settings.performance_degradation_warning_threshold * 100:.0f}% relative "
        f"change, degraded >= {settings.performance_degradation_severe_threshold * 100:.0f}%)."
    )
