"""Lightweight, model-agnostic feature importance.

No SHAP - see app/ml/__init__.py's module map for why. Permutation
importance (sklearn.inspection.permutation_importance) is used uniformly
across every candidate model, because it works identically regardless of
whether the underlying estimator exposes `feature_importances_`/`coef_` at
all: it measures how much a metric degrades when one feature's values are
randomly shuffled, on held-out data the model hasn't been fit on.

Every task module passes the *full* fitted Pipeline (preprocessing + model)
as the estimator, and the *raw* (pre-transform) test dataframe as X - so
importances come back keyed by the original column names a user actually
recognizes ("category", not "categorical__category_Electronics").

Language rule: importance describes what a feature is *associated with* in
the model's predictions, never what it *causes*. "high recency associated
with churn," never "high recency causes churn."
"""

import numpy as np
from sklearn.inspection import permutation_importance

from app.ml.schemas import FeatureImportanceOut


def compute_permutation_importance(
    estimator,
    X_test,
    y_test,
    feature_names: list[str],
    *,
    scoring: str,
    random_seed: int,
    n_repeats: int = 10,
) -> list[FeatureImportanceOut]:
    result = permutation_importance(
        estimator, X_test, y_test, scoring=scoring, n_repeats=n_repeats, random_state=random_seed
    )
    importances = result.importances_mean
    order = np.argsort(importances)[::-1]
    return [
        FeatureImportanceOut(feature=feature_names[i], importance=round(float(importances[i]), 5))
        for i in order
    ]


def linear_coefficient_directions(
    coefficients: np.ndarray, feature_names: list[str]
) -> dict[str, str]:
    """Linear models only: the sign of a coefficient is a technically
    defensible "direction" (a positive coefficient means a higher feature
    value is associated with a higher predicted probability of the positive
    class). Never computed for tree models, where "direction" isn't a
    well-defined single number."""
    return {
        name: ("positive" if coef > 0 else "negative" if coef < 0 else "neutral")
        for name, coef in zip(feature_names, coefficients, strict=True)
    }
