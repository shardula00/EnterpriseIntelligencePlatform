"""Unit tests for app/mlops/drift.py - the PSI-based statistics themselves,
independent of any DB/API. Uses real numeric assertions against known
distributions, not just "it returned something."""

import numpy as np
import pandas as pd
import pytest

from app.config import Settings
from app.mlops.drift import (
    compute_categorical_feature_drift,
    compute_drift,
    compute_numeric_feature_drift,
)

settings = Settings()


def test_numeric_drift_is_near_zero_for_identical_distributions():
    rng = np.random.default_rng(1)
    baseline = pd.Series(rng.normal(50, 10, 1000))
    current = pd.Series(rng.normal(50, 10, 1000))
    result = compute_numeric_feature_drift("amount", baseline, current, settings)
    assert result.method == "psi"
    assert result.statistic < settings.drift_psi_warning_threshold
    assert result.status == "stable"


def test_numeric_drift_flags_a_large_mean_shift():
    rng = np.random.default_rng(1)
    baseline = pd.Series(rng.normal(50, 10, 1000))
    current = pd.Series(rng.normal(150, 30, 1000))
    result = compute_numeric_feature_drift("amount", baseline, current, settings)
    assert result.statistic >= settings.drift_psi_severe_threshold
    assert result.status == "drift"


def test_numeric_drift_baseline_summary_reports_real_statistics():
    baseline = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
    current = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
    result = compute_numeric_feature_drift("x", baseline, current, settings)
    assert result.baseline_summary["mean"] == 30.0
    assert result.baseline_summary["min"] == 10.0
    assert result.baseline_summary["max"] == 50.0
    assert result.baseline_summary["count"] == 5


def test_numeric_drift_handles_missing_values_without_crashing():
    baseline = pd.Series([1.0, 2.0, 3.0, np.nan, np.nan])
    current = pd.Series([np.nan] * 10)
    result = compute_numeric_feature_drift("x", baseline, current, settings)
    assert result.baseline_summary["missing_rate"] == 0.4
    assert result.current_summary["missing_rate"] == 1.0
    # No non-missing current values - not a crash, a well-defined result.
    assert result.status in {"stable", "warning", "drift"}


def test_numeric_drift_on_constant_baseline_uses_deviation_fraction_not_psi():
    baseline = pd.Series([5.0] * 200)
    current_same = pd.Series([5.0] * 200)
    result_same = compute_numeric_feature_drift("x", baseline, current_same, settings)
    assert result_same.method == "constant_value_deviation"
    assert result_same.statistic == 0.0
    assert result_same.status == "stable"

    current_different = pd.Series([500.0] * 200)
    result_diff = compute_numeric_feature_drift("x", baseline, current_different, settings)
    assert result_diff.statistic == 1.0
    assert result_diff.status == "drift"


def test_numeric_drift_with_no_baseline_values_reports_unknown():
    baseline = pd.Series([np.nan, np.nan])
    current = pd.Series([1.0, 2.0, 3.0])
    result = compute_numeric_feature_drift("x", baseline, current, settings)
    assert result.status == "unknown"
    assert result.method == "insufficient_data"


def test_categorical_drift_is_near_zero_for_identical_distributions():
    rng = np.random.default_rng(2)
    categories = ["A", "B", "C", "D"]
    baseline = pd.Series(rng.choice(categories, 1000, p=[0.4, 0.3, 0.2, 0.1]))
    current = pd.Series(rng.choice(categories, 1000, p=[0.4, 0.3, 0.2, 0.1]))
    result = compute_categorical_feature_drift("region", baseline, current, settings)
    assert result.status == "stable"


def test_categorical_drift_flags_a_redistribution():
    rng = np.random.default_rng(2)
    categories = ["A", "B", "C", "D"]
    baseline = pd.Series(rng.choice(categories, 1000, p=[0.7, 0.1, 0.1, 0.1]))
    current = pd.Series(rng.choice(categories, 1000, p=[0.1, 0.1, 0.1, 0.7]))
    result = compute_categorical_feature_drift("region", baseline, current, settings)
    assert result.status == "drift"


def test_categorical_drift_handles_unseen_categories_without_crashing():
    baseline = pd.Series(["A"] * 50 + ["B"] * 50)
    current = pd.Series(["A"] * 20 + ["Z"] * 80)  # "Z" never appeared in baseline
    result = compute_categorical_feature_drift("region", baseline, current, settings)
    assert "Z" in result.current_summary["unseen_categories"]
    assert result.status == "drift"  # a brand-new dominant category is a real shift


def test_categorical_drift_with_no_baseline_values_reports_unknown():
    baseline = pd.Series([None, None], dtype=object)
    current = pd.Series(["A", "B"])
    result = compute_categorical_feature_drift("region", baseline, current, settings)
    assert result.status == "unknown"


def test_compute_drift_overall_status_is_worst_of_its_features():
    baseline_df = pd.DataFrame({"stable_col": [1, 2, 3, 4, 5] * 40, "drifted_col": [1.0] * 200})
    current_df = pd.DataFrame({"stable_col": [1, 2, 3, 4, 5] * 40, "drifted_col": [500.0] * 200})
    result = compute_drift(
        baseline_df, current_df, ["stable_col", "drifted_col"],
        {"stable_col": "numeric", "drifted_col": "numeric"}, settings,
    )
    assert result.overall_status == "drift"
    assert result.total_features_checked == 2
    assert result.drifted_feature_count == 1
    statuses = {f.feature: f.status for f in result.features}
    assert statuses["stable_col"] == "stable"
    assert statuses["drifted_col"] == "drift"


def test_compute_drift_dispatches_numeric_vs_categorical_by_column_type():
    baseline_df = pd.DataFrame({"amount": [10.0, 20.0], "region": ["A", "B"]})
    current_df = pd.DataFrame({"amount": [10.0, 20.0], "region": ["A", "B"]})
    result = compute_drift(
        baseline_df, current_df, ["amount", "region"],
        {"amount": "numeric", "region": "categorical"}, settings,
    )
    types = {f.feature: f.feature_type for f in result.features}
    assert types == {"amount": "numeric", "region": "categorical"}


def test_thresholds_are_configurable_via_settings():
    strict_settings = Settings(drift_psi_warning_threshold=0.01, drift_psi_severe_threshold=0.02)
    rng = np.random.default_rng(3)
    baseline = pd.Series(rng.normal(50, 10, 500))
    current = pd.Series(rng.normal(52, 10, 500))  # a small, real shift
    lenient = compute_numeric_feature_drift("x", baseline, current, settings)
    strict = compute_numeric_feature_drift("x", baseline, current, strict_settings)
    # Same underlying statistic, different status under different thresholds.
    assert lenient.statistic == strict.statistic
    assert lenient.status in {"stable", "warning"}
    assert strict.status == "drift"


@pytest.mark.parametrize("bins", [3, 20])
def test_numeric_drift_bin_count_is_configurable(bins):
    # A large sample keeps per-bin counts stable even at bins=20, so this
    # asserts the real behavior (same distribution -> stable) rather than
    # being sensitive to finite-sample bin noise.
    rng = np.random.default_rng(4)
    baseline = pd.Series(rng.normal(50, 10, 5000))
    current = pd.Series(rng.normal(50, 10, 5000))
    result = compute_numeric_feature_drift("x", baseline, current, settings, bins=bins)
    assert result.status == "stable"
