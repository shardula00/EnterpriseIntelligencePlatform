"""Unit tests for app/mlops/monitoring.py - per-task performance checks
against synthetic data with a known data-generating process (reusing
tests/ml/helpers.py, the same fixtures Phase 5's own task-module tests
use)."""

import pytest

from app.config import Settings
from app.ml.anomaly_detection import train_anomaly
from app.ml.classification import train_classification
from app.ml.forecasting import train_forecast
from app.ml.segmentation import train_segmentation
from app.mlops import monitoring
from app.mlops.errors import InsufficientDataForMonitoringError
from app.models.ml_run import MLRun
from tests.ml.helpers import (
    anomaly_dataframe,
    churn_columns,
    churn_dataframe,
    sales_timeseries_dataframe,
    segmentation_dataframe,
)

settings = Settings()


def _fake_run(task_type: str, configuration: dict, results) -> MLRun:
    return MLRun(
        dataset_id=None, task_type=task_type, model_name="test", configuration=configuration,
        results=results.model_dump(),
    )


def _train_churn_model(n: int = 300, seed: int = 42):
    df = churn_dataframe(n=n)
    columns = churn_columns()
    results, artifact = train_classification(
        df, columns, target_column="churned", feature_columns=["tenure_months", "support_tickets"],
        test_size=0.25, random_seed=seed,
    )
    run = _fake_run("classification", {"target_column": "churned"}, results)
    return results, artifact, run


def _train_forecast_model(n: int = 150, horizon: int = 14, seed: int = 42):
    df = sales_timeseries_dataframe(n=n)
    results, artifact = train_forecast(
        df, datetime_column="order_date", target_column="sales_amount",
        horizon=horizon, random_seed=seed,
    )
    config = {"datetime_column": "order_date", "target_column": "sales_amount"}
    run = _fake_run("forecasting", config, results)
    return results, artifact, run


def _train_segmentation_model(seed: int = 42):
    df = segmentation_dataframe()
    results, artifact = train_segmentation(
        df, feature_columns=["income", "spend"], n_clusters=2, random_seed=seed
    )
    run = _fake_run("segmentation", {"feature_columns": ["income", "spend"]}, results)
    return df, results, artifact, run


def _train_anomaly_model(seed: int = 42):
    df = anomaly_dataframe()
    results, artifact = train_anomaly(
        df, feature_columns=["amount", "distance"], contamination=0.05, random_seed=seed
    )
    run = _fake_run("anomaly_detection", {"feature_columns": ["amount", "distance"]}, results)
    return df, results, artifact, run


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def test_classification_check_reports_a_real_metric_comparison():
    results, artifact, run = _train_churn_model()
    new_df = churn_dataframe(n=200, seed=5)

    check = monitoring.check_classification_performance(artifact, new_df, run, settings)
    assert check.ground_truth_available is True
    assert check.primary_metric == "roc_auc"
    assert check.baseline_value == round(results.metrics["roc_auc"], 4)
    assert 0.0 <= check.current_value <= 1.0
    assert check.status in {"stable", "warning", "degraded"}
    assert "accuracy" in check.extra_metrics


def test_classification_check_detects_real_degradation_when_target_is_shuffled():
    _, artifact, run = _train_churn_model()

    shuffled = churn_dataframe(n=300, seed=7)
    shuffled["churned"] = shuffled["churned"].sample(frac=1, random_state=1).reset_index(drop=True)
    check = monitoring.check_classification_performance(artifact, shuffled, run, settings)
    assert check.status == "degraded"
    assert check.relative_change < -settings.performance_degradation_severe_threshold


def test_classification_check_raises_on_missing_target_column():
    _, artifact, run = _train_churn_model(n=200)
    new_df = churn_dataframe(n=200, seed=5)

    dropped = new_df.drop(columns=["churned"])
    with pytest.raises(InsufficientDataForMonitoringError, match="does not contain the target"):
        monitoring.check_classification_performance(artifact, dropped, run, settings)


def test_classification_check_raises_when_only_one_class_present():
    _, artifact, run = _train_churn_model(n=200)
    new_df = churn_dataframe(n=200, seed=5)

    single_class = new_df.copy()
    single_class["churned"] = False
    with pytest.raises(InsufficientDataForMonitoringError, match="only one class"):
        monitoring.check_classification_performance(artifact, single_class, run, settings)


# ---------------------------------------------------------------------------
# Forecasting
# ---------------------------------------------------------------------------


def test_forecast_check_reports_a_real_mae_comparison():
    results, artifact, run = _train_forecast_model()
    future = sales_timeseries_dataframe(n=170).tail(20)

    check = monitoring.check_forecast_performance(artifact, future, run, settings)
    assert check.ground_truth_available is True
    assert check.primary_metric == "mae"
    assert check.baseline_value == round(results.metrics["mae"], 4)
    assert check.current_value >= 0


def test_forecast_check_raises_when_columns_missing():
    _, artifact, run = _train_forecast_model()
    future = sales_timeseries_dataframe(n=170).tail(20)

    dropped = future.drop(columns=["sales_amount"])
    with pytest.raises(InsufficientDataForMonitoringError, match="must contain both"):
        monitoring.check_forecast_performance(artifact, dropped, run, settings)


# ---------------------------------------------------------------------------
# Segmentation - no ground truth
# ---------------------------------------------------------------------------


def test_segmentation_check_has_no_ground_truth_but_reports_a_real_signal():
    df, results, artifact, run = _train_segmentation_model()

    check = monitoring.check_segmentation_performance(artifact, df, run, settings)
    assert check.ground_truth_available is False
    assert check.primary_metric == "silhouette_score"
    assert check.baseline_value == round(results.silhouette_score, 4)
    assert "no ground truth" in check.explanation.lower()


def test_segmentation_check_raises_when_too_few_rows():
    df, _, artifact, run = _train_segmentation_model()

    with pytest.raises(InsufficientDataForMonitoringError):
        monitoring.check_segmentation_performance(artifact, df.head(1), run, settings)


# ---------------------------------------------------------------------------
# Anomaly detection - no ground truth
# ---------------------------------------------------------------------------


def test_anomaly_check_has_no_ground_truth_but_reports_rate_shift():
    df, results, artifact, run = _train_anomaly_model()

    check = monitoring.check_anomaly_performance(artifact, df, run, settings)
    assert check.ground_truth_available is False
    assert check.primary_metric == "anomaly_percentage"
    assert check.baseline_value == round(results.anomaly_percentage, 4)
    assert "no ground truth" in check.explanation.lower()


def test_anomaly_check_flags_a_real_rate_shift():
    df, _, artifact, run = _train_anomaly_model()

    # Every row now looks like the extreme "anomalous" tail of the training
    # distribution - the flagged rate should shift noticeably.
    shifted = df.copy()
    shifted["amount"] = 900.0
    shifted["distance"] = 90.0
    check = monitoring.check_anomaly_performance(artifact, shifted, run, settings)
    assert check.current_value > check.baseline_value
    assert check.status in {"warning", "degraded"}


# ---------------------------------------------------------------------------
# Threshold configurability
# ---------------------------------------------------------------------------


def test_performance_degradation_thresholds_are_configurable():
    _, artifact, run = _train_churn_model()
    new_df = churn_dataframe(n=200, seed=5)

    lenient = Settings(
        performance_degradation_warning_threshold=0.99,
        performance_degradation_severe_threshold=0.999,
    )
    strict = Settings(
        performance_degradation_warning_threshold=0.001,
        performance_degradation_severe_threshold=0.002,
    )

    lenient_check = monitoring.check_classification_performance(artifact, new_df, run, lenient)
    strict_check = monitoring.check_classification_performance(artifact, new_df, run, strict)
    assert lenient_check.current_value == strict_check.current_value  # same metric
    assert lenient_check.status == "stable"
    assert strict_check.status in {"warning", "degraded"}
