"""Tests for app/agents/ml_agent.py against a real Postgres."""

import pytest

from app.agents import ml_agent
from app.config import Settings
from app.ingestion import service as ingestion_service
from tests.conftest import FIXTURES_DIR, _create_user_with_role

TIMESERIES_SAMPLE = (FIXTURES_DIR / "ml_sales_timeseries_sample.csv").read_bytes()
ORDERS_SAMPLE = (FIXTURES_DIR / "orders_sample.csv").read_bytes()


@pytest.fixture
def forecastable_dataset(db_session):
    return ingestion_service.ingest_upload(
        db_session, Settings(), "ml_sales_timeseries_sample.csv", TIMESERIES_SAMPLE
    )


@pytest.fixture
def too_small_dataset(db_session):
    # orders_sample.csv has 20 rows - below MIN_ROWS_FORECASTING (30) - see
    # app/ml/suitability.py.
    return ingestion_service.ingest_upload(db_session, Settings(), "orders_sample.csv", ORDERS_SAMPLE)


@pytest.fixture
def analyst(db_session):
    return _create_user_with_role(db_session, "ANALYST")


def test_run_trains_a_forecast_for_a_suitable_dataset(db_session, forecastable_dataset, analyst):
    context: dict = {}
    result = ml_agent.run(
        db_session, Settings(), analyst, "forecast the next 30 days", forecastable_dataset.id, context
    )

    assert result.agent == "ml"
    assert [o.tool for o in result.outcomes] == ["check_suitability", "forecast"]
    suitability_outcome, forecast_outcome = result.outcomes
    assert suitability_outcome.data["suitable"] is True
    assert forecast_outcome.allowed is True
    assert forecast_outcome.data["task_type"] == "forecasting"
    assert "run_id" in forecast_outcome.data
    assert context["ml_run_id"] == forecast_outcome.data["run_id"]


def test_run_honors_the_next_quarter_horizon_hint(db_session, forecastable_dataset, analyst):
    context: dict = {}
    result = ml_agent.run(
        db_session, Settings(), analyst, "forecast next quarter's revenue",
        forecastable_dataset.id, context,
    )
    forecast_outcome = result.outcomes[1]
    assert forecast_outcome.data["horizon"] == 13


def test_run_reports_unsuitability_honestly_without_training_anything(
    db_session, too_small_dataset, analyst
):
    context: dict = {}
    result = ml_agent.run(
        db_session, Settings(), analyst, "forecast next month", too_small_dataset.id, context
    )

    assert len(result.outcomes) == 1  # never attempted to train
    assert result.outcomes[0].data["suitable"] is False
    assert "ml_run_id" not in context


def test_run_without_a_dataset_id_explains_one_is_needed(db_session, analyst):
    context: dict = {}
    result = ml_agent.run(db_session, Settings(), analyst, "forecast revenue", None, context)
    assert "dataset" in result.outcomes[0].summary.lower()


def test_suitability_denied_without_ml_read_permission(db_session, forecastable_dataset):
    user = _create_user_with_role(db_session, "VIEWER")
    user.roles = []
    db_session.commit()

    context: dict = {}
    result = ml_agent.run(
        db_session, Settings(), user, "forecast revenue", forecastable_dataset.id, context
    )
    assert result.outcomes[0].allowed is False


def test_forecast_denied_without_ml_train_permission_but_suitability_still_reported(
    db_session, forecastable_dataset
):
    viewer = _create_user_with_role(db_session, "VIEWER")  # has ml:read, not ml:train

    context: dict = {}
    result = ml_agent.run(
        db_session, Settings(), viewer, "forecast revenue", forecastable_dataset.id, context
    )
    suitability_outcome, forecast_outcome = result.outcomes
    assert suitability_outcome.allowed is True
    assert suitability_outcome.data["suitable"] is True
    assert forecast_outcome.allowed is False
    assert "ml_run_id" not in context
