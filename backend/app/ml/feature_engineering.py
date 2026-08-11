"""Reusable feature preprocessing, shared across all four ML tasks.

LEAKAGE PREVENTION (the rule every task module follows): every builder here
returns an *unfitted* sklearn ColumnTransformer/Pipeline. Callers always
call `.fit_transform(X_train)` on the training split first, then
`.transform(X_test)` (never `.fit()` again) on the test/validation split
and on any later prediction data. The preprocessor's learned state (median/
most-frequent values for imputation, one-hot categories, the scaler's
mean/std) therefore only ever reflects the training rows - the test split
never influences how it was fit, and can't leak information back into it.
The task modules (classification.py, segmentation.py, anomaly_detection.py)
enforce this by construction: they never call `fit`/`fit_transform` on data
that includes anything from the held-out split.
"""

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.models.dataset import DatasetColumn

NUMERIC_TYPES = {"integer", "float"}
CATEGORICAL_TYPES = {"text", "boolean"}


def split_numeric_categorical(
    columns: list[DatasetColumn], feature_columns: list[str]
) -> tuple[list[str], list[str]]:
    """Splits `feature_columns` into (numeric, categorical), in a fixed
    order that build_column_preprocessor's ColumnTransformer always follows
    (numeric block first) - shared so callers that need to map a fitted
    linear model's coef_ back to raw column names (see explainability.py's
    use in classification.py) stay in sync with the transformer's actual
    column ordering instead of duplicating and risking drift."""
    by_name = {c.column_name: c for c in columns}
    numeric_cols = [n for n in feature_columns if by_name[n].detected_type in NUMERIC_TYPES]
    categorical_cols = [n for n in feature_columns if by_name[n].detected_type in CATEGORICAL_TYPES]
    return numeric_cols, categorical_cols


def build_column_preprocessor(
    columns: list[DatasetColumn], feature_columns: list[str], *, scale_numeric: bool
) -> ColumnTransformer:
    """Numeric columns: median imputation (+ optional standard scaling).
    Categorical columns: most-frequent imputation + one-hot encoding
    (unknown categories at predict time are ignored, not an error).
    """
    numeric_cols, categorical_cols = split_numeric_categorical(columns, feature_columns)

    numeric_steps = [("impute", SimpleImputer(strategy="median"))]
    if scale_numeric:
        numeric_steps.append(("scale", StandardScaler()))
    numeric_pipeline = Pipeline(numeric_steps)

    categorical_pipeline = Pipeline(
        [
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )

    transformers = []
    if numeric_cols:
        transformers.append(("numeric", numeric_pipeline, numeric_cols))
    if categorical_cols:
        transformers.append(("categorical", categorical_pipeline, categorical_cols))

    return ColumnTransformer(transformers=transformers, remainder="drop")


def get_output_feature_names(preprocessor: ColumnTransformer) -> list[str]:
    """Human-readable names for a *fitted* preprocessor's output columns
    (one-hot columns expanded, e.g. "categorical__category_Electronics")."""
    return [str(name) for name in preprocessor.get_feature_names_out()]


def drop_constant_columns(
    df: pd.DataFrame, feature_columns: list[str]
) -> tuple[pd.DataFrame, list[str]]:
    """Defensive re-check: Phase 2's profiling already excludes constant
    columns from auto-suggestions, but a caller can force one explicitly, or
    downsampling could coincidentally leave a column constant in the sampled
    rows even though it wasn't in the full dataset. Either way, a column
    that's constant in the data actually being trained on carries no signal
    and is dropped, with the fact recorded by the caller (never silent)."""
    dropped = [col for col in feature_columns if df[col].nunique(dropna=True) <= 1]
    kept = [col for col in feature_columns if col not in dropped]
    return df, kept


def extract_calendar_features(dates: pd.Series, start_index: int = 0) -> pd.DataFrame:
    """Simple calendar features from an already-chronologically-sorted
    datetime series - used by forecasting's feature engineering.
    `time_index` counts up from `start_index`, so this can be called once
    over a full history (start_index=0) and again for a single future row
    continuing that same trend index during recursive forecasting (see
    forecasting.py) without resetting to 0."""
    parsed = pd.to_datetime(dates).reset_index(drop=True)
    return pd.DataFrame(
        {
            "day_of_week": parsed.dt.dayofweek,
            "day_of_month": parsed.dt.day,
            "month": parsed.dt.month,
            "quarter": parsed.dt.quarter,
            "time_index": range(start_index, start_index + len(parsed)),
        }
    )
