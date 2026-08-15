"""Tests for app/agents/risk_agent.py.

_flags_from_forecast() is tested with hand-crafted results dicts (pure
Python, no database) for precise, deterministic threshold coverage;
assess_risk()/_flags_from_monitoring() are tested against a real Postgres,
reusing real MLRun/ModelVersion/MonitoringEvent rows the same way
app/mlops/service.py itself already produces them - risk_agent.py never
recomputes drift/performance statistics, only re-surfaces what's already
there, so these tests insert a MonitoringEvent directly rather than
re-deriving real drift (already covered by tests/mlops/*).
"""

from types import SimpleNamespace

import pytest

from app.agents import risk_agent
from app.config import Settings
from app.ingestion import service as ingestion_service
from app.ml.schemas import ForecastTrainRequest
from app.ml.service import train_forecast_run
from app.mlops.service import register_model_version
from app.models.monitoring_event import MonitoringEvent
from tests.conftest import FIXTURES_DIR, _create_user_with_role

TIMESERIES_SAMPLE = (FIXTURES_DIR / "ml_sales_timeseries_sample.csv").read_bytes()


def _fake_run(**results):
    return SimpleNamespace(task_type="forecasting", results=results)


# ---------------------------------------------------------------------------
# _flags_from_forecast - pure Python, precise thresholds
# ---------------------------------------------------------------------------


def test_sharp_decline_is_flagged_critical():
    run = _fake_run(
        forecast=[{"value": 100.0, "lower": None, "upper": None}, {"value": 80.0, "lower": None, "upper": None}],
        has_confidence_interval=False,
    )
    flags = risk_agent._flags_from_forecast(run)
    trend_flags = [f for f in flags if f.source == "forecast_trend"]
    assert trend_flags and trend_flags[0].severity == "critical"


def test_mild_decline_is_flagged_warning():
    run = _fake_run(
        forecast=[{"value": 100.0, "lower": None, "upper": None}, {"value": 93.0, "lower": None, "upper": None}],
        has_confidence_interval=False,
    )
    flags = risk_agent._flags_from_forecast(run)
    trend_flags = [f for f in flags if f.source == "forecast_trend"]
    assert trend_flags and trend_flags[0].severity == "warning"


def test_stable_or_rising_forecast_has_no_trend_flag():
    run = _fake_run(
        forecast=[{"value": 100.0, "lower": None, "upper": None}, {"value": 105.0, "lower": None, "upper": None}],
        has_confidence_interval=False,
    )
    flags = risk_agent._flags_from_forecast(run)
    assert not [f for f in flags if f.source == "forecast_trend"]


def test_wide_confidence_interval_is_flagged_critical():
    run = _fake_run(
        forecast=[{"value": 100.0, "lower": 40.0, "upper": 100.0}],  # 60% width
        has_confidence_interval=True,
    )
    flags = risk_agent._flags_from_forecast(run)
    ci_flags = [f for f in flags if f.source == "forecast_uncertainty"]
    assert ci_flags and ci_flags[0].severity == "critical"


def test_narrow_confidence_interval_has_no_uncertainty_flag():
    run = _fake_run(
        forecast=[{"value": 100.0, "lower": 98.0, "upper": 102.0}],  # 4% width
        has_confidence_interval=True,
    )
    flags = risk_agent._flags_from_forecast(run)
    assert not [f for f in flags if f.source == "forecast_uncertainty"]


def test_missing_confidence_interval_is_flagged_info():
    run = _fake_run(
        forecast=[{"value": 100.0, "lower": None, "upper": None}], has_confidence_interval=False,
    )
    flags = risk_agent._flags_from_forecast(run)
    ci_flags = [f for f in flags if f.source == "forecast_uncertainty"]
    assert ci_flags and ci_flags[0].severity == "info"


def test_non_forecasting_run_produces_no_flags():
    run = SimpleNamespace(task_type="classification", results={})
    assert risk_agent._flags_from_forecast(run) == []


def test_empty_forecast_produces_no_flags():
    run = _fake_run(forecast=[], has_confidence_interval=True)
    assert risk_agent._flags_from_forecast(run) == []


# ---------------------------------------------------------------------------
# assess_risk() / _flags_from_monitoring() - real Postgres
# ---------------------------------------------------------------------------


@pytest.fixture
def analyst(db_session):
    return _create_user_with_role(db_session, "ANALYST")


@pytest.fixture
def dataset(db_session):
    return ingestion_service.ingest_upload(
        db_session, Settings(), "ml_sales_timeseries_sample.csv", TIMESERIES_SAMPLE
    )


def test_assess_risk_with_no_signals_reports_none_detected(db_session, dataset, analyst):
    outcome = risk_agent.assess_risk(db_session, analyst, dataset.id, ml_run_id=None)
    assert outcome.allowed is True
    assert outcome.data["overall_severity"] == "info"
    assert outcome.data["flags"][0]["source"] == "none"


def test_assess_risk_reads_a_real_forecast_run(db_session, dataset, analyst):
    settings = Settings()
    request = ForecastTrainRequest(
        dataset_id=dataset.id, datetime_column="order_date", target_column="sales_amount", horizon=14,
    )
    run = train_forecast_run(db_session, settings, request, analyst.id)

    outcome = risk_agent.assess_risk(db_session, analyst, dataset.id, ml_run_id=str(run.id))
    assert outcome.allowed is True
    assert outcome.data["overall_severity"] in ("info", "warning", "critical")
    assert outcome.data["flags"]  # always at least one flag (even if just "no signals")


def test_assess_risk_surfaces_an_existing_monitoring_event(db_session, dataset, analyst):
    settings = Settings()
    request = ForecastTrainRequest(
        dataset_id=dataset.id, datetime_column="order_date", target_column="sales_amount", horizon=14,
    )
    run = train_forecast_run(db_session, settings, request, analyst.id)
    version = register_model_version(db_session, settings, run.id, analyst.id)

    event = MonitoringEvent(
        model_version_id=version.id,
        dataset_id=dataset.id,
        event_type="drift",
        severity="critical",
        summary="Test critical drift event for risk agent coverage.",
        details={},
        created_by=analyst.id,
    )
    db_session.add(event)
    db_session.commit()

    outcome = risk_agent.assess_risk(db_session, analyst, dataset.id, ml_run_id=None)
    assert outcome.data["overall_severity"] == "critical"
    assert any(f["source"] == "monitoring_event" for f in outcome.data["flags"])


def test_assess_risk_denied_without_mlops_read_permission(db_session, dataset):
    user = _create_user_with_role(db_session, "VIEWER")
    user.roles = []
    db_session.commit()

    outcome = risk_agent.assess_risk(db_session, user, dataset.id, ml_run_id=None)
    assert outcome.allowed is False


def test_assess_risk_ignores_a_run_id_that_no_longer_exists(db_session, dataset, analyst):
    import uuid

    outcome = risk_agent.assess_risk(db_session, analyst, dataset.id, ml_run_id=str(uuid.uuid4()))
    assert outcome.allowed is True  # never raises - a stale run id is not fatal
