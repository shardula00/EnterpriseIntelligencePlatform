"""Anomaly detection via Isolation Forest.

Like segmentation, this is unsupervised - fit directly on all provided
feature rows, no train/test split (there's no ground truth "is this row
anomalous" label to hold out and validate against; the model's own score
is the output). `contamination` is the caller's estimate of what fraction
of rows are expected to be anomalous, used only to set the score threshold
that separates "anomaly" from "normal" - it does not change the underlying
per-row scores themselves.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from app.ml.errors import InvalidMlConfigurationError
from app.ml.feature_engineering import drop_constant_columns
from app.ml.schemas import AnomalyRecordOut, AnomalyResultsOut

MAX_ANOMALOUS_RECORDS_RETURNED = 100


class AnomalyArtifact:
    def __init__(self, pipeline: Pipeline, feature_columns: list[str]):
        self.pipeline = pipeline
        self.feature_columns = feature_columns


def _score_and_label(pipeline: Pipeline, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    # decision_function: higher = more normal, lower/negative = more
    # anomalous. Negated so "anomaly_score" reads intuitively (higher =
    # more anomalous), matching how the frontend presents it.
    raw_scores = pipeline.decision_function(X)
    anomaly_scores = -raw_scores
    is_anomaly = pipeline.predict(X) == -1
    return anomaly_scores, is_anomaly


def train_anomaly(
    df: pd.DataFrame, *, feature_columns: list[str], contamination: float, random_seed: int
) -> tuple[AnomalyResultsOut, AnomalyArtifact]:
    df, feature_columns = drop_constant_columns(df, feature_columns)
    if not feature_columns:
        raise InvalidMlConfigurationError(
            "At least 1 usable feature column is required after removing constant columns."
        )

    X = df[feature_columns]
    pipeline = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median")),
            (
                "isolation_forest",
                IsolationForest(
                    contamination=contamination, random_state=random_seed, n_estimators=200
                ),
            ),
        ]
    )
    pipeline.fit(X)

    scores, is_anomaly = _score_and_label(pipeline, X)
    anomaly_count = int(is_anomaly.sum())

    anomalous_indices = np.argsort(scores)[::-1][:anomaly_count][:MAX_ANOMALOUS_RECORDS_RETURNED]
    anomalous_records = [
        AnomalyRecordOut(
            row_index=int(df.index[i]),
            anomaly_score=round(float(scores[i]), 4),
            is_anomaly=True,
            values={col: _to_plain(df.iloc[i][col]) for col in feature_columns},
        )
        for i in anomalous_indices
    ]

    results = AnomalyResultsOut(
        feature_columns=feature_columns,
        contamination=contamination,
        anomaly_count=anomaly_count,
        anomaly_percentage=round(100 * anomaly_count / len(df), 2),
        anomalous_records=anomalous_records,
        score_summary={
            "min": round(float(scores.min()), 4),
            "max": round(float(scores.max()), 4),
            "mean": round(float(scores.mean()), 4),
        },
        random_seed=random_seed,
        was_sampled=False,
    )
    artifact = AnomalyArtifact(pipeline=pipeline, feature_columns=feature_columns)
    return results, artifact


def predict_anomaly(artifact: AnomalyArtifact, df: pd.DataFrame) -> list[dict]:
    X = df[artifact.feature_columns]
    scores, is_anomaly = _score_and_label(artifact.pipeline, X)
    return [
        {"row_index": int(idx), "anomaly_score": round(float(score), 4), "is_anomaly": bool(flag)}
        for idx, score, flag in zip(df.index, scores, is_anomaly, strict=True)
    ]


def _to_plain(value):
    if isinstance(value, np.generic):
        return value.item()
    if pd.isna(value):
        return None
    return value
