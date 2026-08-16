"""Tests for app/agents/decision_agent.py against a real Postgres."""

import pytest

from app.agents import decision_agent
from app.agents.base import AgentOutcome, ToolOutcome
from app.config import Settings
from app.ingestion import service as ingestion_service
from tests.conftest import FIXTURES_DIR, _create_user_with_role

FINANCE_SAMPLE = (FIXTURES_DIR / "decision_finance_sample.csv").read_bytes()


@pytest.fixture
def analyst(db_session):
    return _create_user_with_role(db_session, "ANALYST")


@pytest.fixture
def finance_dataset(db_session):
    return ingestion_service.ingest_upload(
        db_session, Settings(), "decision_finance_sample.csv", FINANCE_SAMPLE
    )


def test_run_falls_back_to_scenario_when_no_ml_or_risk_context(db_session, finance_dataset, analyst):
    result = decision_agent.run(
        db_session, Settings(), analyst,
        "What happens to profit if revenue decreases by 10%?",
        finance_dataset.id, prior_outcomes=[],
    )
    assert result.agent == "decision"
    assert result.outcomes[0].tool == "scenario"
    assert result.outcomes[0].data["computed"] is True
    assert result.outcomes[0].data["relationship"] == "profit = revenue - cost"


def test_run_proposes_a_recommendation_when_ml_context_is_present(db_session, finance_dataset, analyst):
    prior = [
        AgentOutcome(
            agent="ml",
            outcomes=[
                ToolOutcome(
                    tool="forecast", allowed=True, summary="Trained a forecast, trending down from 100 to 80.",
                    data={"run_id": "r1", "has_confidence_interval": True},
                )
            ],
        )
    ]
    result = decision_agent.run(
        db_session, Settings(), analyst, "recommend an action", finance_dataset.id, prior_outcomes=prior,
    )
    assert result.outcomes[0].tool == "propose"
    assert result.outcomes[0].data["status"] == "pending"


def test_run_proposes_a_recommendation_when_only_risk_context_is_present(
    db_session, finance_dataset, analyst
):
    prior = [
        AgentOutcome(
            agent="risk",
            outcomes=[
                ToolOutcome(
                    tool="assess_risk", allowed=True, summary="[warning] ...",
                    data={"overall_severity": "warning", "flags": []},
                )
            ],
        )
    ]
    result = decision_agent.run(
        db_session, Settings(), analyst, "recommend an action", finance_dataset.id, prior_outcomes=prior,
    )
    assert result.outcomes[0].tool == "propose"


def test_run_without_a_dataset_id_explains_one_is_needed(db_session, analyst):
    result = decision_agent.run(
        db_session, Settings(), analyst, "recommend an action", None, prior_outcomes=[],
    )
    assert "dataset" in result.outcomes[0].summary.lower()


def test_run_denied_without_decision_propose_permission(db_session, finance_dataset):
    viewer = _create_user_with_role(db_session, "VIEWER")  # has decision:read, not decision:propose
    result = decision_agent.run(
        db_session, Settings(), viewer, "recommend an action", finance_dataset.id, prior_outcomes=[],
    )
    assert result.outcomes[0].allowed is False
