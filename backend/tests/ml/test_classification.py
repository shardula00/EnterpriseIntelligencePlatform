"""Unit tests for app/ml/classification.py against synthetic data with a
known data-generating process (tests/ml/helpers.churn_dataframe): high
tenure lowers churn odds, many support tickets raises them. Assertions
check real numeric outcomes, not just "the function returned something."
"""

import pandas as pd
import pytest

from app.ml.classification import predict_classification, train_classification
from app.ml.errors import InvalidMlConfigurationError
from tests.ml.helpers import churn_columns, churn_dataframe, make_column


def test_train_classification_selects_by_roc_auc_and_beats_random_guessing():
    df = churn_dataframe(n=300)
    columns = churn_columns()
    results, artifact = train_classification(
        df,
        columns,
        target_column="churned",
        feature_columns=["tenure_months", "support_tickets", "monthly_charges"],
        test_size=0.25,
        random_seed=42,
    )
    assert results.primary_metric == "roc_auc"
    # A real, learnable signal should comfortably beat a coin flip (0.5).
    assert results.metrics["roc_auc"] > 0.65
    assert results.selected_model == max(
        results.candidate_models, key=lambda c: c.metrics["roc_auc"]
    ).model_name
    assert len(results.candidate_models) == 3
    assert results.confusion_matrix.matrix != []
    assert len(results.sample_predictions) > 0


def test_train_classification_evaluates_on_a_genuinely_held_out_split():
    """Confirms metrics/confusion-matrix are computed over the *held-out*
    test split, not the full dataset: the confusion matrix's total must
    equal the requested test_size fraction of the row count (± stratified
    rounding), never the full 300 rows."""
    df = churn_dataframe(n=300)
    columns = churn_columns()
    results, _ = train_classification(
        df, columns, target_column="churned",
        feature_columns=["tenure_months", "support_tickets", "monthly_charges"],
        test_size=0.2, random_seed=42,
    )
    confusion_total = sum(sum(row) for row in results.confusion_matrix.matrix)
    expected_test_rows = round(300 * 0.2)
    assert abs(confusion_total - expected_test_rows) <= 1
    assert confusion_total < 300


def test_train_classification_different_seeds_produce_different_splits():
    df = churn_dataframe(n=200)
    columns = churn_columns()
    results_a, _ = train_classification(
        df, columns, target_column="churned", feature_columns=["tenure_months", "support_tickets"],
        test_size=0.3, random_seed=1,
    )
    results_b, _ = train_classification(
        df, columns, target_column="churned", feature_columns=["tenure_months", "support_tickets"],
        test_size=0.3, random_seed=2,
    )
    # Different seeds -> different stratified splits -> generally different
    # sample predictions, proof a real split (not the same rows every time)
    # drives evaluation.
    assert results_a.sample_predictions != results_b.sample_predictions


def test_train_classification_reports_feature_importance_for_every_feature():
    df = churn_dataframe(n=200)
    columns = churn_columns()
    results, _ = train_classification(
        df, columns, target_column="churned",
        feature_columns=["tenure_months", "support_tickets", "monthly_charges"],
        test_size=0.25, random_seed=42,
    )
    reported = {f.feature for f in results.feature_importance}
    assert reported == {"tenure_months", "support_tickets", "monthly_charges"}


def test_train_classification_rejects_non_binary_target_at_runtime():
    df = pd.DataFrame(
        {
            "tenure_months": [1, 2, 3, 4, 5, 6],
            "status": ["A", "B", "C", "A", "B", "C"],  # 3 distinct values in the loaded data
        }
    )
    columns = [
        make_column("tenure_months", "integer"),
        make_column("status", "text"),
    ]
    with pytest.raises(InvalidMlConfigurationError, match="not exactly 2"):
        train_classification(
            df, columns, target_column="status", feature_columns=["tenure_months"],
            test_size=0.3, random_seed=42,
        )


def test_train_classification_drops_constant_feature_columns():
    df = churn_dataframe(n=150)
    df["always_the_same"] = 1
    columns = churn_columns() + [make_column("always_the_same", "integer")]
    results, _ = train_classification(
        df, columns, target_column="churned",
        feature_columns=["tenure_months", "always_the_same"],
        test_size=0.25, random_seed=42,
    )
    assert results.feature_columns == ["tenure_months"]


def test_predict_classification_uses_fitted_artifact_without_retraining():
    df = churn_dataframe(n=200)
    columns = churn_columns()
    _, artifact = train_classification(
        df, columns, target_column="churned",
        feature_columns=["tenure_months", "support_tickets"],
        test_size=0.25, random_seed=42,
    )
    predictions = predict_classification(artifact, df.head(10))
    assert len(predictions) == 10
    for p in predictions:
        assert p["predicted"] in artifact.label_names
        assert 0.0 <= p["probability"] <= 1.0
