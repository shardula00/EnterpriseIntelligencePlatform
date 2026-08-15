"""Unit tests for app/analytics/query_builder.py - pure Python, no
database (build_query only compiles SQLAlchemy Core constructs, it never
connects). Verifies the *shape* of the query/rendered SQL for each
ParsedIntent kind, and that every kind stays within max_rows."""

import uuid

from app.analytics.nl_parser import ParsedIntent
from app.analytics.query_builder import build_query
from app.models.dataset import Dataset, DatasetColumn


def _col(position: int, name: str, detected_type: str) -> DatasetColumn:
    return DatasetColumn(
        position=position,
        original_name=name.title(),
        column_name=name,
        detected_type=detected_type,
        nullable=True,
        null_count=0,
        distinct_count=5,
    )


DATASET = Dataset(
    id=uuid.uuid4(),
    name="phase8_sales",
    original_filename="phase8_sales.csv",
    file_type="csv",
    storage_schema="ingested",
    storage_table_name="ds_test_table",
    row_count=28,
    column_count=9,
    quality_score=100.0,
)
COLUMNS = [
    _col(0, "date", "datetime"),
    _col(1, "product", "text"),
    _col(2, "region", "text"),
    _col(3, "revenue", "integer"),
]


def test_total_intent_builds_a_single_aggregate_select():
    intent = ParsedIntent(kind="total", aggregation="sum", metric_column="revenue")
    built = build_query(DATASET, COLUMNS, intent, max_rows=500)

    assert built.result_columns == ["revenue"]
    assert built.sql_text.upper().startswith("SELECT")
    assert "sum(ingested.ds_test_table.revenue)" in built.sql_text
    assert "GROUP BY" not in built.sql_text.upper()
    assert "ds_test_table" in built.sql_text


def test_total_count_intent_uses_count_star_with_no_metric_column():
    intent = ParsedIntent(kind="total", aggregation="count", metric_column=None)
    built = build_query(DATASET, COLUMNS, intent, max_rows=500)

    assert built.result_columns == ["count"]
    assert "count(*)" in built.sql_text.lower()
    # Regression: a bare func.count() has no table affiliation of its own,
    # so this must be anchored via an explicit select_from(table) - without
    # it, this renders with no FROM clause at all, which sql_guard.py then
    # (correctly) rejects for not referencing the dataset's table.
    assert "FROM" in built.sql_text.upper()
    assert "ds_test_table" in built.sql_text


def test_breakdown_intent_groups_orders_desc_and_caps_at_max_rows():
    intent = ParsedIntent(
        kind="breakdown", aggregation="sum", metric_column="revenue", group_by_column="region"
    )
    built = build_query(DATASET, COLUMNS, intent, max_rows=7)

    assert built.result_columns == ["region", "revenue"]
    upper = built.sql_text.upper()
    assert "GROUP BY" in upper
    assert "ORDER BY" in upper and "DESC" in upper
    assert "LIMIT 7" in upper


def test_top_n_intent_respects_explicit_limit_and_ascending_order():
    intent = ParsedIntent(
        kind="top_n",
        aggregation="sum",
        metric_column="revenue",
        group_by_column="product",
        limit=3,
        descending=False,
    )
    built = build_query(DATASET, COLUMNS, intent, max_rows=500)

    upper = built.sql_text.upper()
    assert "LIMIT 3" in upper
    assert "ASC" in upper or "DESC" not in upper


def test_top_n_intent_limit_is_capped_by_max_rows():
    intent = ParsedIntent(
        kind="top_n",
        aggregation="sum",
        metric_column="revenue",
        group_by_column="product",
        limit=100,
        descending=True,
    )
    built = build_query(DATASET, COLUMNS, intent, max_rows=5)

    assert "LIMIT 5" in built.sql_text.upper()


def test_trend_intent_buckets_by_date_trunc_and_orders_by_period():
    intent = ParsedIntent(
        kind="trend",
        aggregation="sum",
        metric_column="revenue",
        date_column="date",
        granularity="month",
    )
    built = build_query(DATASET, COLUMNS, intent, max_rows=500)

    assert built.result_columns == ["period", "revenue"]
    lowered = built.sql_text.lower()
    assert "date_trunc" in lowered
    assert "'month'" in lowered
    assert "order by period" in lowered


def test_generated_sql_is_always_a_single_select_with_no_semicolon():
    intent = ParsedIntent(kind="total", aggregation="sum", metric_column="revenue")
    built = build_query(DATASET, COLUMNS, intent, max_rows=500)

    assert built.sql_text.strip().upper().startswith("SELECT")
    assert ";" not in built.sql_text
