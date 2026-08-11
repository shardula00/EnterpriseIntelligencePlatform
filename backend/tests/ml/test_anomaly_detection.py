"""Unit tests for app/ml/anomaly_detection.py against synthetic data with 5
injected extreme outliers among 95 normal points (tests/ml/helpers.
anomaly_dataframe) - a working Isolation Forest should flag most of them."""

import pytest

from app.ml.anomaly_detection import predict_anomaly, train_anomaly
from app.ml.errors import InvalidMlConfigurationError
from tests.ml.helpers import anomaly_dataframe


def test_train_anomaly_flags_most_injected_outliers():
    df = anomaly_dataframe()  # rows 95-99 are the injected extreme outliers
    results, artifact = train_anomaly(
        df, feature_columns=["amount", "distance"], contamination=0.05, random_seed=42
    )

    flagged_indices = {r.row_index for r in results.anomalous_records}
    true_anomaly_indices = set(range(95, 100))
    overlap = flagged_indices & true_anomaly_indices
    assert len(overlap) >= 4  # at least 4 of the 5 real outliers caught

    assert results.contamination == 0.05
    assert results.anomaly_count == round(0.05 * 100)


def test_anomalous_records_are_sorted_by_score_descending():
    df = anomaly_dataframe()
    results, _ = train_anomaly(
        df, feature_columns=["amount", "distance"], contamination=0.05, random_seed=42
    )
    scores = [r.anomaly_score for r in results.anomalous_records]
    assert scores == sorted(scores, reverse=True)


def test_anomalous_records_include_the_raw_feature_values():
    df = anomaly_dataframe()
    results, _ = train_anomaly(
        df, feature_columns=["amount", "distance"], contamination=0.05, random_seed=42
    )
    for record in results.anomalous_records:
        assert set(record.values.keys()) == {"amount", "distance"}


def test_train_anomaly_rejects_when_no_features_remain_after_dropping_constants():
    df = anomaly_dataframe()
    df["constant_col"] = 1
    with pytest.raises(InvalidMlConfigurationError):
        train_anomaly(df, feature_columns=["constant_col"], contamination=0.05, random_seed=42)


def test_predict_anomaly_uses_fitted_artifact_without_retraining():
    df = anomaly_dataframe()
    _, artifact = train_anomaly(
        df, feature_columns=["amount", "distance"], contamination=0.05, random_seed=42
    )
    predictions = predict_anomaly(artifact, df.tail(5))  # the 5 known outlier rows
    assert len(predictions) == 5
    anomalous = [p for p in predictions if p["is_anomaly"]]
    assert len(anomalous) >= 3  # most of the known outliers should predict as anomalous
