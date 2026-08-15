"""Tests for app/kg/service.py against a real Postgres - the orchestration
layer app/api/kg.py and app/rag/service.py both call."""

import uuid

import pytest

from app.config import Settings
from app.ingestion import service as ingestion_service
from app.ingestion.errors import DatasetNotFoundError
from app.kg.service import build_graph_for_dataset, retrieve_graph_evidence
from tests.conftest import FIXTURES_DIR

ORDERS_SAMPLE = (FIXTURES_DIR / "orders_sample.csv").read_bytes()


@pytest.fixture
def dataset(db_session):
    return ingestion_service.ingest_upload(db_session, Settings(), "orders_sample.csv", ORDERS_SAMPLE)


def test_build_graph_for_dataset_returns_real_counts(db_session, dataset):
    result = build_graph_for_dataset(db_session, dataset.id)
    assert result.entity_count > 0
    assert result.relationship_count == 20 * 4
    assert "Customer" in result.entity_types
    assert "Order" in result.entity_types


def test_build_graph_for_dataset_raises_for_an_unknown_dataset(db_session):
    with pytest.raises(DatasetNotFoundError):
        build_graph_for_dataset(db_session, uuid.uuid4())


def test_retrieve_graph_evidence_returns_evidence_after_a_build(db_session, dataset):
    build_graph_for_dataset(db_session, dataset.id)
    facts = retrieve_graph_evidence(db_session, "What region is Alice Johnson in?", max_facts=5)
    assert len(facts) == 1


def test_retrieve_graph_evidence_returns_nothing_before_any_build(db_session, dataset):
    # The dataset was ingested but no /graph/build call has happened yet -
    # a normal, honest "nothing to retrieve," not an error.
    facts = retrieve_graph_evidence(db_session, "What region is Alice Johnson in?", max_facts=5)
    assert facts == []
