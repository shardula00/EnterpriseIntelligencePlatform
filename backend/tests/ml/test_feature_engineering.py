"""Unit tests for app/ml/feature_engineering.py, with an emphasis on the
leakage-prevention contract: a preprocessor fit only on a "train" slice
must not have its learned state (imputation values, one-hot categories)
altered by later transforming a "test" slice with different values.
"""

import numpy as np
import pandas as pd

from app.ml.feature_engineering import (
    build_column_preprocessor,
    drop_constant_columns,
    extract_calendar_features,
    get_output_feature_names,
    split_numeric_categorical,
)
from tests.ml.helpers import make_column


def test_split_numeric_categorical_preserves_order_and_splits_by_type():
    columns = [
        make_column("a", "integer"),
        make_column("b", "text"),
        make_column("c", "float"),
        make_column("d", "boolean"),
    ]
    numeric, categorical = split_numeric_categorical(columns, ["a", "b", "c", "d"])
    assert numeric == ["a", "c"]
    assert categorical == ["b", "d"]


def test_build_column_preprocessor_numeric_only_no_scaling():
    columns = [make_column("a", "integer"), make_column("b", "float")]
    df = pd.DataFrame({"a": [1, 2, None, 4], "b": [10.0, 20.0, 30.0, 40.0]})
    preprocessor = build_column_preprocessor(columns, ["a", "b"], scale_numeric=False)
    transformed = preprocessor.fit_transform(df)
    # Median imputation only (no scaling): column "a"'s missing value becomes
    # the median of [1, 2, 4] = 2, and unscaled values are left as-is.
    assert transformed.shape == (4, 2)
    assert transformed[2, 0] == 2.0
    assert transformed[0, 1] == 10.0


def test_build_column_preprocessor_categorical_one_hot_expands_columns():
    columns = [make_column("region", "text")]
    df = pd.DataFrame({"region": ["North", "South", "North"]})
    preprocessor = build_column_preprocessor(columns, ["region"], scale_numeric=False)
    transformed = preprocessor.fit_transform(df)
    names = get_output_feature_names(preprocessor)
    assert transformed.shape == (3, 2)  # one-hot: North, South
    assert any("North" in n for n in names)
    assert any("South" in n for n in names)


def test_preprocessor_fit_on_train_never_relearns_from_test_values():
    """The core leakage-prevention contract: fitting on a train slice, then
    transforming a test slice with an out-of-range numeric value and an
    unseen category, must not change what the preprocessor learned."""
    columns = [make_column("amount", "float"), make_column("region", "text")]
    train = pd.DataFrame({"amount": [10.0, 20.0, 30.0], "region": ["North", "South", "North"]})
    # extreme outlier + unseen category
    test = pd.DataFrame({"amount": [10_000.0], "region": ["Nowhereville"]})

    preprocessor = build_column_preprocessor(columns, ["amount", "region"], scale_numeric=True)
    preprocessor.fit(train)

    numeric_scaler = preprocessor.named_transformers_["numeric"].named_steps["scale"]
    mean_before = numeric_scaler.mean_.copy()

    # Transforming test data must be a pure read of already-fit state - no
    # relearning happens on .transform(), regardless of what the test data
    # contains.
    transformed_test = preprocessor.transform(test)
    assert np.array_equal(numeric_scaler.mean_, mean_before)
    assert transformed_test.shape[0] == 1
    # The unseen category ("Nowhereville") is handled via handle_unknown=
    # "ignore" - all-zero one-hot row, not an error and not a new column.
    categorical_block = transformed_test[:, 1:]
    assert categorical_block.sum() == 0


def test_drop_constant_columns_removes_single_valued_columns():
    df = pd.DataFrame({"a": [1, 1, 1], "b": [1, 2, 3]})
    _, kept = drop_constant_columns(df, ["a", "b"])
    assert kept == ["b"]


def test_drop_constant_columns_keeps_all_when_none_constant():
    df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    _, kept = drop_constant_columns(df, ["a", "b"])
    assert kept == ["a", "b"]


def test_extract_calendar_features_time_index_continues_from_start_index():
    dates = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"])
    features = extract_calendar_features(pd.Series(dates), start_index=10)
    assert list(features["time_index"]) == [10, 11, 12]
    assert features["day_of_week"].iloc[0] == pd.Timestamp("2024-01-01").dayofweek
    assert features["month"].iloc[0] == 1


def test_extract_calendar_features_default_start_index_is_zero():
    dates = pd.to_datetime(["2024-06-01", "2024-06-02"])
    features = extract_calendar_features(pd.Series(dates))
    assert list(features["time_index"]) == [0, 1]
