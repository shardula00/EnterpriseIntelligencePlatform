"""Tests for app/decision/scenario.py against a real Postgres - the
verified-relationship what-if engine.

decision_finance_sample.csv exists specifically because no checked-in
fixture has a verifiable linear relationship among its numeric columns
(the manually-tested phase8_sales dataset from Phase 8's manual
verification isn't a committed fixture - see tests/test_analytics_api.py's
own note on this). The engine itself never assumes profit = revenue -
cost; this fixture's data is constructed so the engine can *discover* it.
"""

import pytest

from app.analytics.query_builder import build_query
from app.analytics.nl_parser import ParsedIntent
from app.config import Settings
from app.decision.scenario import _parse_question, run_scenario
from app.ingestion import service as ingestion_service
from app.models.dataset import DatasetColumn
from tests.conftest import FIXTURES_DIR

FINANCE_SAMPLE = (FIXTURES_DIR / "decision_finance_sample.csv").read_bytes()
ORDERS_SAMPLE = (FIXTURES_DIR / "orders_sample.csv").read_bytes()


def _col(position: int, name: str, detected_type: str) -> DatasetColumn:
    return DatasetColumn(
        position=position, original_name=name.title(), column_name=name, detected_type=detected_type,
        nullable=True, null_count=0, distinct_count=5,
    )


FINANCE_COLUMNS = [
    _col(0, "date", "datetime"),
    _col(1, "product", "text"),
    _col(2, "region", "text"),
    _col(3, "revenue", "integer"),
    _col(4, "cost", "integer"),
    _col(5, "profit", "integer"),
]


# ---------------------------------------------------------------------------
# _parse_question - pure Python, no database
# ---------------------------------------------------------------------------


def test_parse_question_extracts_metrics_direction_and_percent():
    parsed = _parse_question("What happens to profit if revenue decreases by 10%?", FINANCE_COLUMNS)
    assert parsed is not None
    affected, perturbed, percent = parsed
    assert affected.column_name == "profit"
    assert perturbed.column_name == "revenue"
    assert percent == -10.0


def test_parse_question_handles_increase_phrasing():
    parsed = _parse_question("What happens to profit if revenue increases by 20%?", FINANCE_COLUMNS)
    assert parsed is not None
    _, _, percent = parsed
    assert percent == 20.0


def test_parse_question_returns_none_without_a_percent():
    assert _parse_question("What happens to profit if revenue changes?", FINANCE_COLUMNS) is None


def test_parse_question_returns_none_without_a_direction_word():
    # A bare percent with no increase/decrease word is deliberately not
    # guessed at.
    assert _parse_question("What happens to profit if revenue is 10%?", FINANCE_COLUMNS) is None


def test_parse_question_returns_none_when_no_metric_matches():
    assert _parse_question("What happens if the weather decreases by 10%?", FINANCE_COLUMNS) is None


# ---------------------------------------------------------------------------
# run_scenario - integration, real Postgres
# ---------------------------------------------------------------------------


@pytest.fixture
def finance_dataset(db_session):
    return ingestion_service.ingest_upload(
        db_session, Settings(), "decision_finance_sample.csv", FINANCE_SAMPLE
    )


@pytest.fixture
def orders_dataset(db_session):
    return ingestion_service.ingest_upload(db_session, Settings(), "orders_sample.csv", ORDERS_SAMPLE)


def _real_total(db_session, dataset, columns, column_name):
    intent = ParsedIntent(kind="total", aggregation="sum", metric_column=column_name)
    built = build_query(dataset, columns, intent, 500)
    row = db_session.connection().execute(built.statement).one()
    return float(row._mapping[column_name])


def test_run_scenario_verifies_the_real_relationship_and_computes_impact(db_session, finance_dataset):
    columns = sorted(finance_dataset.columns, key=lambda c: c.position)
    result = run_scenario(
        db_session, Settings(), finance_dataset, columns,
        "What happens to profit if revenue decreases by 10%?",
    )

    assert result.computed is True
    assert result.affected_metric == "profit"
    assert result.perturbed_metric == "revenue"
    assert result.delta_percent == -10.0
    assert result.relationship == "profit = revenue - cost"
    assert "linear extrapolation" in result.note
    assert "not a causal or predictive model" in result.note

    real_baseline_revenue = _real_total(db_session, finance_dataset, columns, "revenue")
    real_baseline_profit = _real_total(db_session, finance_dataset, columns, "profit")
    assert result.baseline_perturbed_value == pytest.approx(real_baseline_revenue)
    assert result.baseline_affected_value == pytest.approx(real_baseline_profit)
    assert result.new_perturbed_value == pytest.approx(real_baseline_revenue * 0.9)
    # profit = revenue - cost, so a 10% revenue cut (cost held constant)
    # changes profit by exactly -10% of baseline revenue.
    assert result.affected_value_change == pytest.approx(-0.10 * real_baseline_revenue)


def test_run_scenario_discovers_the_relationship_in_either_column_order(db_session, finance_dataset):
    columns = sorted(finance_dataset.columns, key=lambda c: c.position)
    result = run_scenario(
        db_session, Settings(), finance_dataset, columns,
        "What happens to revenue if cost increases by 5%?",
    )
    assert result.computed is True
    assert result.relationship == "revenue = cost + profit"


def test_run_scenario_declines_when_no_relationship_verifies(db_session, orders_dataset):
    columns = sorted(orders_dataset.columns, key=lambda c: c.position)
    # orders_sample.csv has quantity/unit_price with no third numeric
    # column that makes either a verified sum/difference of the other.
    result = run_scenario(
        db_session, Settings(), orders_dataset, columns,
        "What happens to quantity if unit_price increases by 10%?",
    )
    assert result.computed is False
    assert "No verified relationship" in result.reason


def test_run_scenario_declines_honestly_when_the_question_is_unparseable(db_session, finance_dataset):
    columns = sorted(finance_dataset.columns, key=lambda c: c.position)
    result = run_scenario(db_session, Settings(), finance_dataset, columns, "How is business going?")
    assert result.computed is False
    assert result.reason is not None
    assert result.affected_metric is None
