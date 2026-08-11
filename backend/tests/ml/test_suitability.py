"""Unit tests for app/ml/suitability.py - pure functions over in-memory
Dataset/DatasetColumn objects, no DB needed. Covers both suitability layers:
check_* (task-picker UI) and validate_*_request (what actually gates a
training call).
"""

import pytest

from app.ml import suitability
from app.ml.errors import InvalidMlConfigurationError
from tests.ml.helpers import make_column, make_dataset

# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def test_classification_suitable_dataset_passes():
    columns = [
        make_column("tenure", "integer", distinct_count=50),
        make_column("churned", "boolean", distinct_count=2),
    ]
    dataset = make_dataset(100, columns)
    check = suitability.check_classification(dataset, columns)
    assert check.suitable
    assert check.reasons == []
    assert "churned" in check.suggested_target_columns


def test_classification_rejects_dataset_with_no_binary_target():
    columns = [
        make_column("tenure", "integer", distinct_count=50),
        make_column("region", "text", distinct_count=5),
    ]
    dataset = make_dataset(100, columns)
    check = suitability.check_classification(dataset, columns)
    assert not check.suitable
    assert any("two meaningful classes" in r or "target column" in r for r in check.reasons)


def test_classification_rejects_dataset_with_too_few_rows():
    columns = [
        make_column("tenure", "integer", distinct_count=10),
        make_column("churned", "boolean", distinct_count=2),
    ]
    dataset = make_dataset(5, columns)
    check = suitability.check_classification(dataset, columns)
    assert not check.suitable
    assert any(str(suitability.MIN_ROWS_CLASSIFICATION) in r for r in check.reasons)


def test_classification_rejects_when_target_is_only_usable_column():
    columns = [make_column("churned", "boolean", distinct_count=2)]
    dataset = make_dataset(100, columns)
    check = suitability.check_classification(dataset, columns)
    assert not check.suitable
    assert any("No usable feature columns" in r for r in check.reasons)


def test_validate_classification_request_rejects_unknown_target():
    columns = [make_column("churned", "boolean", distinct_count=2)]
    with pytest.raises(InvalidMlConfigurationError, match="Unknown column"):
        suitability.validate_classification_request(columns, "does_not_exist", None)


def test_validate_classification_request_rejects_non_binary_target():
    columns = [make_column("region", "text", distinct_count=5)]
    with pytest.raises(InvalidMlConfigurationError, match="two meaningful classes"):
        suitability.validate_classification_request(columns, "region", None)


def test_validate_classification_request_rejects_target_as_feature():
    columns = [
        make_column("tenure", "integer", distinct_count=50),
        make_column("churned", "boolean", distinct_count=2),
    ]
    with pytest.raises(InvalidMlConfigurationError, match="cannot also be a feature"):
        suitability.validate_classification_request(columns, "churned", ["churned"])


def test_validate_classification_request_defaults_to_suggested_features():
    columns = [
        make_column("tenure", "integer", distinct_count=50),
        make_column("churned", "boolean", distinct_count=2),
    ]
    resolved = suitability.validate_classification_request(columns, "churned", None)
    assert resolved == ["tenure"]


# ---------------------------------------------------------------------------
# Forecasting
# ---------------------------------------------------------------------------


def test_forecasting_suitable_dataset_passes():
    columns = [
        make_column("order_date", "datetime", distinct_count=100),
        make_column("sales", "float", distinct_count=100),
    ]
    dataset = make_dataset(100, columns)
    check = suitability.check_forecasting(dataset, columns)
    assert check.suitable
    assert check.suggested_datetime_columns == ["order_date"]


def test_forecasting_rejects_dataset_with_no_datetime_column():
    columns = [make_column("sales", "float", distinct_count=100)]
    dataset = make_dataset(100, columns)
    check = suitability.check_forecasting(dataset, columns)
    assert not check.suitable
    assert any("no datetime column was detected" in r for r in check.reasons)


def test_forecasting_rejects_dataset_with_no_numeric_target():
    columns = [
        make_column("order_date", "datetime", distinct_count=100),
        make_column("region", "text", distinct_count=4),
    ]
    dataset = make_dataset(100, columns)
    check = suitability.check_forecasting(dataset, columns)
    assert not check.suitable
    assert any("non-constant numeric column" in r for r in check.reasons)


def test_validate_forecast_request_rejects_non_datetime_column():
    columns = [
        make_column("region", "text", distinct_count=4),
        make_column("sales", "float", distinct_count=100),
    ]
    with pytest.raises(InvalidMlConfigurationError, match="not a datetime column"):
        suitability.validate_forecast_request(columns, "region", "sales")


def test_validate_forecast_request_rejects_non_numeric_target():
    columns = [
        make_column("order_date", "datetime", distinct_count=100),
        make_column("region", "text", distinct_count=4),
    ]
    with pytest.raises(InvalidMlConfigurationError, match="not numeric"):
        suitability.validate_forecast_request(columns, "order_date", "region")


def test_validate_forecast_request_rejects_same_column_twice():
    # A column can't simultaneously be typed "datetime" (required for
    # datetime_column) and numeric (required for target_column), so passing
    # the same name for both is caught by the numeric-type check rather
    # than ever reaching the explicit "must be different" guard - still a
    # rejection either way, which is what matters here.
    columns = [make_column("order_date", "datetime", distinct_count=100)]
    with pytest.raises(InvalidMlConfigurationError, match="not numeric"):
        suitability.validate_forecast_request(columns, "order_date", "order_date")


# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------


def test_segmentation_suitable_dataset_passes():
    columns = [
        make_column("income", "float", distinct_count=80),
        make_column("spend", "float", distinct_count=80),
    ]
    dataset = make_dataset(80, columns)
    check = suitability.check_segmentation(dataset, columns)
    assert check.suitable


def test_segmentation_rejects_fewer_than_2_numeric_columns():
    columns = [make_column("income", "float", distinct_count=80)]
    dataset = make_dataset(80, columns)
    check = suitability.check_segmentation(dataset, columns)
    assert not check.suitable
    assert any("at least 2 non-constant numeric" in r for r in check.reasons)


def test_validate_segmentation_request_rejects_non_numeric_feature():
    columns = [
        make_column("income", "float", distinct_count=80),
        make_column("region", "text", distinct_count=4),
    ]
    with pytest.raises(InvalidMlConfigurationError, match="must be numeric"):
        suitability.validate_segmentation_request(columns, ["income", "region"])


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------


def test_anomaly_suitable_dataset_passes():
    columns = [make_column("amount", "float", distinct_count=80)]
    dataset = make_dataset(20, columns)
    check = suitability.check_anomaly(dataset, columns)
    assert check.suitable


def test_anomaly_rejects_dataset_with_no_numeric_columns():
    columns = [make_column("region", "text", distinct_count=4)]
    dataset = make_dataset(80, columns)
    check = suitability.check_anomaly(dataset, columns)
    assert not check.suitable
    assert any("at least 1 non-constant numeric" in r for r in check.reasons)


def test_anomaly_rejects_dataset_with_too_few_rows():
    columns = [make_column("amount", "float", distinct_count=10)]
    dataset = make_dataset(5, columns)
    check = suitability.check_anomaly(dataset, columns)
    assert not check.suitable


# ---------------------------------------------------------------------------
# check_all_tasks
# ---------------------------------------------------------------------------


def test_check_all_tasks_returns_all_four_task_types():
    columns = [
        make_column("order_date", "datetime", distinct_count=100),
        make_column("amount", "float", distinct_count=100),
        make_column("churned", "boolean", distinct_count=2),
    ]
    dataset = make_dataset(100, columns)
    checks = suitability.check_all_tasks(dataset, columns)
    assert set(checks.keys()) == {
        "classification",
        "forecasting",
        "segmentation",
        "anomaly_detection",
    }
