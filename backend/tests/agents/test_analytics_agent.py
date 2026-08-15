"""Tests for app/agents/analytics_agent.py against a real Postgres."""

import pytest

from app.agents import analytics_agent
from app.config import Settings
from app.ingestion import service as ingestion_service
from tests.conftest import FIXTURES_DIR, _create_user_with_role

ORDERS_SAMPLE = (FIXTURES_DIR / "orders_sample.csv").read_bytes()


@pytest.fixture
def dataset(db_session):
    return ingestion_service.ingest_upload(db_session, Settings(), "orders_sample.csv", ORDERS_SAMPLE)


@pytest.fixture
def analyst(db_session):
    return _create_user_with_role(db_session, "ANALYST")


def test_ask_answers_a_real_question(db_session, dataset, analyst):
    outcome = analytics_agent.ask(
        db_session, Settings(), analyst, "What is the total quantity?", dataset.id
    )
    assert outcome.allowed is True
    assert outcome.data["status"] == "answered"
    assert outcome.data["rows"][0]["quantity"] == 65


def test_ask_without_a_dataset_id_explains_one_is_needed(db_session, analyst):
    outcome = analytics_agent.ask(db_session, Settings(), analyst, "What is the total quantity?", None)
    assert outcome.allowed is True
    assert outcome.data is None
    assert "dataset" in outcome.summary.lower()


def test_ask_denied_without_analytics_query_permission(db_session, dataset):
    viewer = _create_user_with_role(db_session, "VIEWER")
    outcome = analytics_agent.ask(
        db_session, Settings(), viewer, "What is the total quantity?", dataset.id
    )
    assert outcome.allowed is False
