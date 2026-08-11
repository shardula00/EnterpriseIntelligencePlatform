"""Pure unit tests for the column-selection logic in app/bi/service.py.

No database needed - these test which columns get suggested as breakdown/
trend candidates given a dataset's column metadata, not the SQL itself
(that's covered by tests/test_kpis_api.py against a live Postgres).
"""

from app.bi.service import suggested_breakdown_columns, suggested_trend_columns
from app.models.dataset import DatasetColumn


def _column(name: str, detected_type: str, distinct_count: int = 5) -> DatasetColumn:
    return DatasetColumn(
        column_name=name,
        original_name=name,
        position=0,
        detected_type=detected_type,
        nullable=True,
        null_count=0,
        distinct_count=distinct_count,
    )


def test_low_cardinality_text_column_is_a_breakdown_candidate():
    columns = [_column("region", "text", distinct_count=4)]
    assert suggested_breakdown_columns(columns, row_count=20) == ["region"]


def test_high_cardinality_text_column_is_not_a_breakdown_candidate():
    columns = [_column("customer_name", "text", distinct_count=500)]
    assert suggested_breakdown_columns(columns, row_count=500) == []


def test_near_unique_column_is_excluded_even_under_the_absolute_cap():
    # 20 rows, 20 distinct values: every row is its own "category" - this
    # clears the absolute cap (<=20) but groups nothing, so it must still
    # be excluded.
    columns = [_column("customer_name", "text", distinct_count=20)]
    assert suggested_breakdown_columns(columns, row_count=20) == []


def test_constant_column_is_not_a_breakdown_candidate():
    # distinct_count == 1 carries no grouping information.
    columns = [_column("country", "text", distinct_count=1)]
    assert suggested_breakdown_columns(columns, row_count=20) == []


def test_numeric_column_is_not_a_breakdown_candidate():
    columns = [_column("amount", "integer", distinct_count=4)]
    assert suggested_breakdown_columns(columns, row_count=20) == []


def test_boolean_column_is_a_breakdown_candidate():
    columns = [_column("is_priority", "boolean", distinct_count=2)]
    assert suggested_breakdown_columns(columns, row_count=20) == ["is_priority"]


def test_datetime_column_is_a_trend_candidate():
    columns = [_column("order_date", "datetime", distinct_count=20)]
    assert suggested_trend_columns(columns) == ["order_date"]


def test_non_datetime_columns_are_not_trend_candidates():
    columns = [_column("region", "text"), _column("amount", "integer")]
    assert suggested_trend_columns(columns) == []


def test_suggestions_preserve_column_order():
    columns = [
        _column("region", "text", distinct_count=4),
        _column("amount", "integer"),
        _column("category", "text", distinct_count=3),
    ]
    assert suggested_breakdown_columns(columns, row_count=20) == ["region", "category"]
