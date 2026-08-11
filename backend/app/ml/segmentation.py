"""Unsupervised customer/record segmentation via K-Means.

Fit on all provided feature rows directly - unlike classification/
forecasting, there's no held-out "correct answer" to validate a cluster
assignment against; the assignment itself is the model's output. Features
are median-imputed then scaled (K-Means is distance-based, so an unscaled
feature with a larger numeric range would dominate the distance
calculation regardless of its actual importance).
"""

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.ml.errors import InvalidMlConfigurationError
from app.ml.feature_engineering import drop_constant_columns
from app.ml.schemas import ClusterProfileOut, SegmentationResultsOut


class SegmentationArtifact:
    def __init__(self, pipeline: Pipeline, feature_columns: list[str]):
        self.pipeline = pipeline
        self.feature_columns = feature_columns


def train_segmentation(
    df: pd.DataFrame, *, feature_columns: list[str], n_clusters: int, random_seed: int
) -> tuple[SegmentationResultsOut, SegmentationArtifact]:
    df, feature_columns = drop_constant_columns(df, feature_columns)
    if len(feature_columns) < 2:
        raise InvalidMlConfigurationError(
            "At least 2 usable feature columns are required after removing constant columns."
        )

    X = df[feature_columns]
    if len(X) <= n_clusters:
        raise InvalidMlConfigurationError(
            f"n_clusters ({n_clusters}) must be smaller than the number of rows ({len(X)})."
        )

    pipeline = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("kmeans", KMeans(n_clusters=n_clusters, random_state=random_seed, n_init=10)),
        ]
    )
    labels = pipeline.fit_predict(X)

    # Slicing re-uses the already-fitted impute/scale steps (no refit) - a
    # normal, safe way to get intermediate output from a fitted Pipeline.
    scaled_X = pipeline[:-1].transform(X)
    score = float(silhouette_score(scaled_X, labels)) if len(set(labels)) > 1 else 0.0

    cluster_sizes = {str(i): int((labels == i).sum()) for i in range(n_clusters)}

    labeled = df[feature_columns].copy()
    labeled["_cluster"] = labels
    profiles = [
        ClusterProfileOut(
            cluster=i,
            size=int((labels == i).sum()),
            feature_means={
                col: round(float(labeled.loc[labeled["_cluster"] == i, col].mean()), 4)
                for col in feature_columns
            },
        )
        for i in range(n_clusters)
    ]

    # Centers are reported back in the features' ORIGINAL units (via the
    # fitted scaler's inverse_transform), not standard-deviation units - a
    # raw scaled number like "-0.3" means nothing to a non-technical viewer.
    scaler: StandardScaler = pipeline.named_steps["scale"]
    centers_original = scaler.inverse_transform(pipeline.named_steps["kmeans"].cluster_centers_)

    results = SegmentationResultsOut(
        feature_columns=feature_columns,
        n_clusters=n_clusters,
        silhouette_score=round(score, 4),
        cluster_sizes=cluster_sizes,
        cluster_profiles=profiles,
        cluster_centers=centers_original.round(4).tolist(),
        random_seed=random_seed,
        was_sampled=False,
    )
    artifact = SegmentationArtifact(pipeline=pipeline, feature_columns=feature_columns)
    return results, artifact


def predict_segmentation(artifact: SegmentationArtifact, df: pd.DataFrame) -> list[dict]:
    X = df[artifact.feature_columns]
    labels = artifact.pipeline.predict(X)
    return [
        {"row_index": int(idx), "cluster": int(label)}
        for idx, label in zip(df.index, labels, strict=True)
    ]
