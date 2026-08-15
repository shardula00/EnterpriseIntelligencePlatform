"""Unit tests for app/analytics/nl_parser.py - pure Python, no database.

Uses a realistic 9-column sales-shaped schema (matching the real
phase8_sales fixture: date/product/category/region/quantity/revenue/cost/
profit/customer) purely as *test data*, never as logic the parser itself
special-cases - see nl_parser.py's own docstring on why nothing there is
dataset-specific.
"""

import pytest

from app.analytics.errors import UnsupportedQuestionError
from app.analytics.nl_parser import ParsedIntent, parse
from app.models.dataset import DatasetColumn


def _col(position: int, original: str, name: str, detected_type: str) -> DatasetColumn:
    return DatasetColumn(
        position=position,
        original_name=original,
        column_name=name,
        detected_type=detected_type,
        nullable=True,
        null_count=0,
        distinct_count=5,
    )


SALES_COLUMNS = [
    _col(0, "Date", "date", "datetime"),
    _col(1, "Product", "product", "text"),
    _col(2, "Category", "category", "text"),
    _col(3, "Region", "region", "text"),
    _col(4, "Quantity", "quantity", "integer"),
    _col(5, "Revenue", "revenue", "integer"),
    _col(6, "Cost", "cost", "integer"),
    _col(7, "Profit", "profit", "integer"),
    _col(8, "Customer", "customer", "text"),
]


def test_total_question_matches_the_exact_column_named_in_the_question():
    intent = parse("What is the total revenue?", SALES_COLUMNS)
    assert intent == ParsedIntent(kind="total", aggregation="sum", metric_column="revenue")


def test_total_question_resolves_a_synonym_not_the_columns_own_name():
    # "sales" isn't any column's real name - it's revenue's synonym.
    intent = parse("What is the total sales?", SALES_COLUMNS)
    assert intent.kind == "total"
    assert intent.metric_column == "revenue"


def test_breakdown_question_groups_by_the_named_category():
    intent = parse("Show total sales by region.", SALES_COLUMNS)
    assert intent == ParsedIntent(
        kind="breakdown", aggregation="sum", metric_column="revenue", group_by_column="region"
    )


def test_breakdown_recognizes_average_and_a_different_category():
    intent = parse("average profit by category", SALES_COLUMNS)
    assert intent == ParsedIntent(
        kind="breakdown", aggregation="avg", metric_column="profit", group_by_column="category"
    )


def test_which_category_generated_the_highest_metric_is_top_n_ranked_by_sum():
    # "highest revenue" means "greatest total revenue," not a literal
    # per-row MAX - see nl_parser.py's comment on this.
    intent = parse("Which product generated the highest revenue?", SALES_COLUMNS)
    assert intent == ParsedIntent(
        kind="top_n",
        aggregation="sum",
        metric_column="revenue",
        group_by_column="product",
        limit=1,
        descending=True,
    )


def test_which_category_has_the_lowest_metric_ranks_ascending():
    intent = parse("Which region has the lowest profit?", SALES_COLUMNS)
    assert intent.kind == "top_n"
    assert intent.descending is False
    assert intent.group_by_column == "region"


def test_which_category_has_the_lowest_average_metric_keeps_average_not_sum():
    intent = parse("Which region has the lowest average profit?", SALES_COLUMNS)
    assert intent.aggregation == "avg"
    assert intent.descending is False


def test_top_n_pattern_with_explicit_count():
    intent = parse("top 3 products by revenue", SALES_COLUMNS)
    assert intent == ParsedIntent(
        kind="top_n",
        aggregation="sum",
        metric_column="revenue",
        group_by_column="product",
        limit=3,
        descending=True,
    )


def test_monthly_trend_question_uses_the_datetime_column():
    intent = parse("What are the monthly sales?", SALES_COLUMNS)
    assert intent == ParsedIntent(
        kind="trend",
        aggregation="sum",
        metric_column="revenue",
        date_column="date",
        granularity="month",
    )


def test_weekly_trend_is_recognized_distinctly_from_monthly():
    intent = parse("weekly revenue trend", SALES_COLUMNS)
    assert intent.kind == "trend"
    assert intent.granularity == "week"


def test_count_question_needs_no_metric_column():
    intent = parse("How many orders are there?", SALES_COLUMNS)
    assert intent == ParsedIntent(kind="total", aggregation="count", metric_column=None)


def test_parsing_is_case_and_whitespace_insensitive():
    intent = parse("   WHAT Is The   TOTAL Revenue?  ", SALES_COLUMNS)
    assert intent.kind == "total"
    assert intent.metric_column == "revenue"


def test_unsupported_question_raises_when_no_column_matches():
    with pytest.raises(UnsupportedQuestionError):
        parse("What is the weather like today?", SALES_COLUMNS)


def test_unsupported_question_raises_for_an_empty_string():
    with pytest.raises(UnsupportedQuestionError):
        parse("   ", SALES_COLUMNS)


def test_trend_falls_back_to_total_when_dataset_has_no_datetime_column():
    columns_without_date = [c for c in SALES_COLUMNS if c.detected_type != "datetime"]
    intent = parse("monthly revenue", columns_without_date)
    assert intent.kind == "total"
    assert intent.metric_column == "revenue"
