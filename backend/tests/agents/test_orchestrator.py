"""Tests for app/agents/orchestrator.py against a real Postgres - the
full route -> invoke -> compose pipeline, including the Phase 10 DoD
scenario itself."""

import pytest

from app.agents.orchestrator import UNSUPPORTED_MESSAGE, run
from app.config import Settings
from app.ingestion import service as ingestion_service
from tests.conftest import FIXTURES_DIR, _create_user_with_role

TIMESERIES_SAMPLE = (FIXTURES_DIR / "ml_sales_timeseries_sample.csv").read_bytes()
ORDERS_SAMPLE = (FIXTURES_DIR / "orders_sample.csv").read_bytes()


@pytest.fixture
def analyst(db_session):
    return _create_user_with_role(db_session, "ANALYST")


@pytest.fixture
def forecastable_dataset(db_session):
    return ingestion_service.ingest_upload(
        db_session, Settings(), "ml_sales_timeseries_sample.csv", TIMESERIES_SAMPLE
    )


@pytest.fixture
def orders_dataset(db_session):
    return ingestion_service.ingest_upload(db_session, Settings(), "orders_sample.csv", ORDERS_SAMPLE)


def test_the_phase_10_dod_scenario_end_to_end(db_session, forecastable_dataset, analyst):
    """'forecast next quarter's revenue and flag any risk factors': router
    -> ml agent -> forecast -> risk agent -> deterministic risk flags ->
    composed final response."""
    result = run(
        db_session, Settings(), analyst,
        "Forecast next quarter's revenue and flag any risk factors.",
        forecastable_dataset.id,
    )

    assert result.status == "answered"
    assert result.agents_invoked == ["ml", "risk"]
    assert [ao.agent for ao in result.agent_outcomes] == ["ml", "risk"]

    ml_outcome, risk_outcome = result.agent_outcomes
    assert [o.tool for o in ml_outcome.outcomes] == ["check_suitability", "forecast"]
    forecast_tool_outcome = ml_outcome.outcomes[1]
    assert forecast_tool_outcome.allowed is True
    assert forecast_tool_outcome.data["horizon"] == 13  # "next quarter" hint

    assert [o.tool for o in risk_outcome.outcomes] == ["assess_risk"]
    risk_tool_outcome = risk_outcome.outcomes[0]
    assert risk_tool_outcome.allowed is True
    assert risk_tool_outcome.data["overall_severity"] in ("info", "warning", "critical")

    # The composed summary threads both agents' own outcome summaries.
    assert forecast_tool_outcome.summary in result.summary
    assert risk_tool_outcome.summary in result.summary


def test_unsupported_question_returns_an_honest_explanation_not_a_guess(db_session, analyst):
    result = run(db_session, Settings(), analyst, "asdkjfh qpwoeiru nonsense", None)
    assert result.status == "unsupported"
    assert result.agents_invoked == []
    assert result.agent_outcomes == []
    assert result.summary == UNSUPPORTED_MESSAGE


def test_analytics_only_scenario(db_session, orders_dataset, analyst):
    result = run(db_session, Settings(), analyst, "What is the total quantity?", orders_dataset.id)
    assert result.status == "answered"
    assert result.agents_invoked == ["analytics"]
    assert result.agent_outcomes[0].outcomes[0].data["rows"][0]["quantity"] == 65


def test_data_only_scenario(db_session, orders_dataset, analyst):
    result = run(db_session, Settings(), analyst, "List datasets available.", None)
    assert result.status == "answered"
    assert result.agents_invoked == ["data"]


def test_research_only_scenario(db_session, analyst):
    result = run(db_session, Settings(), analyst, "What does the handbook policy say?", None)
    assert result.status == "answered"
    assert result.agents_invoked == ["research"]


def test_risk_alone_uses_only_monitoring_evidence_when_no_forecast_ran(
    db_session, orders_dataset, analyst
):
    result = run(db_session, Settings(), analyst, "Any risk factors for this dataset?", orders_dataset.id)
    assert result.agents_invoked == ["risk"]
    assert result.agent_outcomes[0].outcomes[0].data["overall_severity"] == "info"


def test_permission_filtering_end_to_end_for_a_viewer(db_session, forecastable_dataset):
    viewer = _create_user_with_role(db_session, "VIEWER")  # ml:read yes, ml:train no

    result = run(
        db_session, Settings(), viewer,
        "Forecast next quarter's revenue and flag any risk factors.",
        forecastable_dataset.id,
    )

    ml_outcome, risk_outcome = result.agent_outcomes
    suitability_outcome, forecast_outcome = ml_outcome.outcomes
    assert suitability_outcome.allowed is True  # viewer has ml:read
    assert forecast_outcome.allowed is False  # viewer lacks ml:train
    # risk still ran (mlops:read is granted to VIEWER) but had no forecast to read.
    assert risk_outcome.outcomes[0].allowed is True
