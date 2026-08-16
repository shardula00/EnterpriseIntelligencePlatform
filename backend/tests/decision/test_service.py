"""Tests for app/decision/service.py against a real Postgres."""

import uuid

import pytest

from app.agents.base import AgentOutcome, ToolOutcome
from app.config import Settings
from app.decision import service
from app.decision.errors import InvalidDecisionActionError, RecommendationNotFoundError
from app.ingestion import service as ingestion_service
from app.ingestion.errors import DatasetNotFoundError
from app.ml.schemas import ForecastTrainRequest
from app.ml.service import train_forecast_run
from tests.conftest import FIXTURES_DIR, _create_user_with_role

FINANCE_SAMPLE = (FIXTURES_DIR / "decision_finance_sample.csv").read_bytes()
TIMESERIES_SAMPLE = (FIXTURES_DIR / "ml_sales_timeseries_sample.csv").read_bytes()


@pytest.fixture
def analyst(db_session):
    return _create_user_with_role(db_session, "ANALYST")


@pytest.fixture
def admin(db_session):
    return _create_user_with_role(db_session, "ADMIN")


@pytest.fixture
def finance_dataset(db_session):
    return ingestion_service.ingest_upload(
        db_session, Settings(), "decision_finance_sample.csv", FINANCE_SAMPLE
    )


@pytest.fixture
def timeseries_dataset(db_session):
    return ingestion_service.ingest_upload(
        db_session, Settings(), "ml_sales_timeseries_sample.csv", TIMESERIES_SAMPLE
    )


# ---------------------------------------------------------------------------
# propose_recommendation
# ---------------------------------------------------------------------------


def test_propose_with_prior_outcomes_uses_them_as_evidence(db_session, finance_dataset, analyst):
    ml_outcome = AgentOutcome(
        agent="ml",
        outcomes=[
            ToolOutcome(
                tool="forecast", allowed=True, summary="Trained a forecast, trending down from 100 to 80.",
                data={"run_id": str(uuid.uuid4()), "has_confidence_interval": True},
            )
        ],
    )
    risk_outcome = AgentOutcome(
        agent="risk",
        outcomes=[
            ToolOutcome(
                tool="assess_risk", allowed=True, summary="[warning] declining trend",
                data={"overall_severity": "warning", "flags": [{"severity": "warning", "message": "m", "source": "forecast_trend"}]},
            )
        ],
    )

    record = service.propose_recommendation(
        db_session, Settings(), analyst, finance_dataset.id, "recommend an action",
        prior_outcomes=[ml_outcome, risk_outcome],
    )

    assert record.status == "pending"
    assert record.confidence == "medium"
    assert len(record.evidence) == 2
    assert {e["agent"] for e in record.evidence} == {"ml", "risk"}
    assert record.risks == risk_outcome.outcomes[0].data["flags"]


def test_propose_falls_back_to_the_latest_forecast_run_with_no_prior_outcomes(
    db_session, timeseries_dataset, analyst
):
    request = ForecastTrainRequest(
        dataset_id=timeseries_dataset.id, datetime_column="order_date",
        target_column="sales_amount", horizon=14,
    )
    run = train_forecast_run(db_session, Settings(), request, analyst.id)

    record = service.propose_recommendation(
        db_session, Settings(), analyst, timeseries_dataset.id, "recommend an action",
    )

    assert any(e["agent"] == "ml" and e["data"]["run_id"] == str(run.id) for e in record.evidence)
    assert any(e["agent"] == "risk" for e in record.evidence)


def test_propose_with_no_ml_history_at_all_is_still_honest_not_fabricated(
    db_session, finance_dataset, analyst
):
    record = service.propose_recommendation(
        db_session, Settings(), analyst, finance_dataset.id, "recommend an action",
    )
    assert record.evidence == []
    assert any("no forecast was available" in a.lower() for a in record.assumptions)


def test_propose_attaches_a_verified_scenario_as_expected_impact(db_session, finance_dataset, analyst):
    record = service.propose_recommendation(
        db_session, Settings(), analyst, finance_dataset.id,
        "What happens to profit if revenue decreases by 10%?",
    )
    assert record.expected_impact is not None
    assert record.expected_impact["relationship"] == "profit = revenue - cost"


def test_propose_sets_expected_impact_null_when_no_scenario_was_requested(
    db_session, finance_dataset, analyst
):
    record = service.propose_recommendation(
        db_session, Settings(), analyst, finance_dataset.id, "recommend an action",
    )
    assert record.expected_impact is None


def test_propose_raises_dataset_not_found_for_an_unknown_dataset(db_session, analyst):
    with pytest.raises(DatasetNotFoundError):
        service.propose_recommendation(db_session, Settings(), analyst, uuid.uuid4(), "recommend")


# ---------------------------------------------------------------------------
# run_scenario_only
# ---------------------------------------------------------------------------


def test_run_scenario_only_is_never_persisted(db_session, finance_dataset):
    before = len(service.list_recommendations(db_session, dataset_id=finance_dataset.id))
    service.run_scenario_only(
        db_session, Settings(), finance_dataset.id, "What happens to profit if revenue decreases by 10%?"
    )
    after = len(service.list_recommendations(db_session, dataset_id=finance_dataset.id))
    assert after == before


# ---------------------------------------------------------------------------
# approve / reject lifecycle
# ---------------------------------------------------------------------------


def test_approve_sets_status_and_decider(db_session, finance_dataset, analyst, admin):
    record = service.propose_recommendation(db_session, Settings(), analyst, finance_dataset.id, "recommend")
    approved = service.approve_recommendation(db_session, record.id, admin)

    assert approved.status == "approved"
    assert approved.decided_by == admin.id
    assert approved.decided_at is not None


def test_reject_sets_status_and_decider(db_session, finance_dataset, analyst, admin):
    record = service.propose_recommendation(db_session, Settings(), analyst, finance_dataset.id, "recommend")
    rejected = service.reject_recommendation(db_session, record.id, admin)

    assert rejected.status == "rejected"
    assert rejected.decided_by == admin.id


def test_deciding_an_already_decided_recommendation_raises(db_session, finance_dataset, analyst, admin):
    record = service.propose_recommendation(db_session, Settings(), analyst, finance_dataset.id, "recommend")
    service.approve_recommendation(db_session, record.id, admin)

    with pytest.raises(InvalidDecisionActionError):
        service.reject_recommendation(db_session, record.id, admin)


def test_get_and_list_recommendations(db_session, finance_dataset, analyst):
    record = service.propose_recommendation(db_session, Settings(), analyst, finance_dataset.id, "recommend")

    fetched = service.get_recommendation(db_session, record.id)
    assert fetched.id == record.id

    listed = service.list_recommendations(db_session, dataset_id=finance_dataset.id)
    assert any(r.id == record.id for r in listed)


def test_get_recommendation_raises_for_an_unknown_id(db_session):
    with pytest.raises(RecommendationNotFoundError):
        service.get_recommendation(db_session, uuid.uuid4())
