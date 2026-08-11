"""Binary classification (e.g. churn prediction).

Candidates: Logistic Regression, Random Forest, HistGradientBoosting - all
scikit-learn, no XGBoost (see app/ml/__init__.py for why). Primary metric:
ROC-AUC, not accuracy - see PRIMARY_METRIC_RATIONALE.

Leakage prevention: each candidate is one sklearn Pipeline
(preprocessing + model); `.fit()` is called once, on the training split
only. Predicting/scoring on the test split only ever calls `.predict*()`,
never `.fit()` again - see feature_engineering.py's module docstring for
the general rule this follows.
"""

from dataclasses import dataclass

import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from app.ml.errors import InvalidMlConfigurationError
from app.ml.evaluation import round_metrics
from app.ml.explainability import compute_permutation_importance, linear_coefficient_directions
from app.ml.feature_engineering import (
    build_column_preprocessor,
    drop_constant_columns,
    split_numeric_categorical,
)
from app.ml.schemas import (
    CandidateModelMetrics,
    ClassificationResultsOut,
    ClassificationSamplePrediction,
    ConfusionMatrixOut,
)
from app.models.dataset import DatasetColumn

PRIMARY_METRIC = "roc_auc"
PRIMARY_METRIC_RATIONALE = (
    "ROC-AUC, not accuracy, decides the winning model: churn-shaped "
    "problems are usually imbalanced (most customers do not churn), so a "
    "model that always predicts 'no churn' can score a deceptively high "
    "accuracy while being useless. ROC-AUC measures how well the model "
    "ranks likely churners above likely non-churners across every decision "
    "threshold, which is what actually matters for prioritizing retention "
    "outreach."
)

MAX_SAMPLE_PREDICTIONS = 20


@dataclass
class ClassificationArtifact:
    """Everything predict() needs later without retraining."""

    pipeline: Pipeline
    feature_columns: list[str]
    label_names: tuple[str, str]  # (negative, positive)


def _build_candidates(random_seed: int) -> list[tuple[str, object]]:
    return [
        ("Logistic Regression", LogisticRegression(max_iter=1000, random_state=random_seed)),
        ("Random Forest", RandomForestClassifier(n_estimators=200, random_state=random_seed)),
        ("Gradient Boosting", HistGradientBoostingClassifier(random_state=random_seed)),
    ]


def train_classification(
    df: pd.DataFrame,
    columns: list[DatasetColumn],
    *,
    target_column: str,
    feature_columns: list[str],
    test_size: float,
    random_seed: int,
) -> tuple[ClassificationResultsOut, ClassificationArtifact]:
    df = df.dropna(subset=[target_column]).reset_index(drop=True)
    df, feature_columns = drop_constant_columns(df, feature_columns)
    if not feature_columns:
        raise InvalidMlConfigurationError(
            "No usable feature columns remain after removing constant columns."
        )

    # A clean two-value string label with a stable (sorted) ordering, so
    # "the positive class" is well-defined regardless of which literal
    # values the column happens to contain (True/False, "Yes"/"No", 0/1).
    y_raw = df[target_column].astype(str)
    label_names = sorted(y_raw.unique())
    if len(label_names) != 2:
        raise InvalidMlConfigurationError(
            f"Target column '{target_column}' has {len(label_names)} distinct "
            f"values in the loaded data, not exactly 2."
        )
    negative_label, positive_label = label_names[0], label_names[1]
    y = (y_raw == positive_label).astype(int)
    X = df[feature_columns]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_seed, stratify=y
    )
    class_distribution = {negative_label: int((y == 0).sum()), positive_label: int((y == 1).sum())}

    candidate_metrics: list[CandidateModelMetrics] = []
    fitted: dict[str, tuple[Pipeline, pd.Series, pd.Series]] = {}

    for name, classifier in _build_candidates(random_seed):
        pipeline = Pipeline(
            [
                (
                    "preprocess",
                    build_column_preprocessor(
                        columns, feature_columns, scale_numeric=(name == "Logistic Regression")
                    ),
                ),
                ("model", classifier),
            ]
        )
        pipeline.fit(X_train, y_train)

        y_pred = pipeline.predict(X_test)
        y_proba = pipeline.predict_proba(X_test)[:, 1]
        metrics = round_metrics(
            {
                "accuracy": accuracy_score(y_test, y_pred),
                "precision": precision_score(y_test, y_pred, zero_division=0),
                "recall": recall_score(y_test, y_pred, zero_division=0),
                "f1": f1_score(y_test, y_pred, zero_division=0),
                "roc_auc": roc_auc_score(y_test, y_proba),
            }
        )
        candidate_metrics.append(CandidateModelMetrics(model_name=name, metrics=metrics))
        fitted[name] = (pipeline, y_pred, y_proba)

    best_name = max(candidate_metrics, key=lambda c: c.metrics[PRIMARY_METRIC]).model_name
    best_pipeline, best_pred, best_proba = fitted[best_name]
    best_metrics = next(c.metrics for c in candidate_metrics if c.model_name == best_name)

    cm = confusion_matrix(y_test, best_pred, labels=[0, 1])
    importance = compute_permutation_importance(
        best_pipeline, X_test, y_test, feature_columns, scoring="roc_auc", random_seed=random_seed
    )

    if best_name == "Logistic Regression":
        numeric_cols, _ = split_numeric_categorical(columns, feature_columns)
        # coef_ follows the ColumnTransformer's output order: the numeric
        # block first, unexpanded (1 coefficient per numeric column) - see
        # split_numeric_categorical's docstring. Categorical (one-hot
        # expanded) coefficients aren't mapped back to a single raw column,
        # so no direction is reported for them.
        raw_coefficients = best_pipeline.named_steps["model"].coef_[0][: len(numeric_cols)]
        directions = linear_coefficient_directions(raw_coefficients, numeric_cols)
        for item in importance:
            if item.feature in directions:
                item.direction = directions[item.feature]

    sample_predictions = [
        ClassificationSamplePrediction(
            row_index=int(idx),
            actual=negative_label if actual == 0 else positive_label,
            predicted=negative_label if pred == 0 else positive_label,
            probability=round(float(proba), 4),
        )
        for idx, actual, pred, proba in list(
            zip(X_test.index, y_test, best_pred, best_proba, strict=True)
        )[:MAX_SAMPLE_PREDICTIONS]
    ]

    results = ClassificationResultsOut(
        target_column=target_column,
        feature_columns=feature_columns,
        class_distribution=class_distribution,
        candidate_models=candidate_metrics,
        selected_model=best_name,
        primary_metric=PRIMARY_METRIC,
        primary_metric_rationale=PRIMARY_METRIC_RATIONALE,
        metrics=best_metrics,
        confusion_matrix=ConfusionMatrixOut(
            labels=[negative_label, positive_label], matrix=cm.tolist()
        ),
        feature_importance=importance,
        sample_predictions=sample_predictions,
        test_size=test_size,
        random_seed=random_seed,
        was_sampled=False,  # set by the caller (service.py) if it downsampled
    )
    artifact = ClassificationArtifact(
        pipeline=best_pipeline,
        feature_columns=feature_columns,
        label_names=(negative_label, positive_label),
    )
    return results, artifact


def predict_classification(artifact: ClassificationArtifact, df: pd.DataFrame) -> list[dict]:
    """Score every row of `df` with an already-fitted artifact."""
    X = df[artifact.feature_columns]
    predictions = artifact.pipeline.predict(X)
    probabilities = artifact.pipeline.predict_proba(X)[:, 1]
    negative_label, positive_label = artifact.label_names
    return [
        {
            "row_index": int(idx),
            "predicted": negative_label if pred == 0 else positive_label,
            "probability": round(float(proba), 4),
        }
        for idx, pred, proba in zip(df.index, predictions, probabilities, strict=True)
    ]
