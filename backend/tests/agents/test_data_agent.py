"""Tests for app/agents/data_agent.py against a real Postgres."""

import pytest

from app.agents import data_agent
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


def test_list_available_datasets_mentions_a_real_dataset(db_session, dataset, analyst):
    outcome = data_agent.list_available_datasets(db_session, analyst)
    assert outcome.allowed is True
    assert dataset.name in outcome.summary
    assert any(d["id"] == str(dataset.id) for d in outcome.data["datasets"])


def test_describe_dataset_returns_kpi_relevant_fields(db_session, dataset, analyst):
    outcome = data_agent.describe_dataset(db_session, analyst, dataset.id)
    assert outcome.allowed is True
    assert outcome.data["row_count"] == dataset.row_count
    assert "quantity" in outcome.data["numeric_columns"]


def test_run_lists_when_no_dataset_id_given(db_session, dataset, analyst):
    result = data_agent.run(db_session, analyst, None)
    assert result.agent == "data"
    assert result.outcomes[0].tool == "list_datasets"


def test_run_describes_when_a_dataset_id_is_given(db_session, dataset, analyst):
    result = data_agent.run(db_session, analyst, dataset.id)
    assert result.outcomes[0].tool == "describe_dataset"


def test_permission_denied_for_a_user_with_no_dataset_read(db_session, dataset):
    user = _create_user_with_role(db_session, "VIEWER")
    user.roles = []  # strip even VIEWER's own dataset:read for this test
    db_session.commit()

    outcome = data_agent.describe_dataset(db_session, user, dataset.id)
    assert outcome.allowed is False
    assert "permission" in outcome.summary.lower()
