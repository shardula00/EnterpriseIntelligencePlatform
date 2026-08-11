"""Unit tests for app/ml/segmentation.py against two well-separated
synthetic blobs (tests/ml/helpers.segmentation_dataframe) - a K-Means model
that actually works should recover very close to a 2-cluster split with a
strong silhouette score."""

import pytest

from app.ml.errors import InvalidMlConfigurationError
from app.ml.segmentation import predict_segmentation, train_segmentation
from tests.ml.helpers import segmentation_dataframe


def test_train_segmentation_recovers_well_separated_clusters():
    df = segmentation_dataframe()
    results, artifact = train_segmentation(
        df, feature_columns=["income", "spend"], n_clusters=2, random_seed=42
    )

    assert results.n_clusters == 2
    # Two well-separated Gaussian blobs should silhouette very strongly.
    assert results.silhouette_score > 0.7
    assert sum(results.cluster_sizes.values()) == 80
    assert len(results.cluster_profiles) == 2
    assert len(results.cluster_centers) == 2


def test_cluster_centers_are_reported_in_original_units_not_standardized():
    df = segmentation_dataframe()
    results, _ = train_segmentation(
        df, feature_columns=["income", "spend"], n_clusters=2, random_seed=42
    )

    # Group A was generated around income~100/spend~20, group B around
    # income~25/spend~80 - centers should land near those raw scales, not
    # near 0 (which is what a standardized-space center would look like).
    incomes = [c[0] for c in results.cluster_centers]
    assert any(80 < income < 120 for income in incomes)
    assert any(10 < income < 40 for income in incomes)


def test_cluster_profiles_feature_means_match_reported_cluster_sizes():
    df = segmentation_dataframe()
    results, _ = train_segmentation(
        df, feature_columns=["income", "spend"], n_clusters=2, random_seed=42
    )
    for profile in results.cluster_profiles:
        assert profile.size == results.cluster_sizes[str(profile.cluster)]
        assert "income" in profile.feature_means
        assert "spend" in profile.feature_means


def test_train_segmentation_rejects_fewer_than_2_feature_columns():
    df = segmentation_dataframe()
    with pytest.raises(InvalidMlConfigurationError):
        train_segmentation(df, feature_columns=["income"], n_clusters=2, random_seed=42)


def test_train_segmentation_rejects_n_clusters_not_smaller_than_row_count():
    df = segmentation_dataframe().head(3)
    with pytest.raises(InvalidMlConfigurationError):
        train_segmentation(df, feature_columns=["income", "spend"], n_clusters=5, random_seed=42)


def test_predict_segmentation_assigns_every_row_to_a_valid_cluster():
    df = segmentation_dataframe()
    _, artifact = train_segmentation(
        df, feature_columns=["income", "spend"], n_clusters=2, random_seed=42
    )
    predictions = predict_segmentation(artifact, df.head(10))
    assert len(predictions) == 10
    for p in predictions:
        assert p["cluster"] in {0, 1}
