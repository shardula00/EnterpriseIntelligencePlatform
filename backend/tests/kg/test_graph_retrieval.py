"""Tests for app/kg/graph_retrieval.py against a real Postgres, using a
graph built from the real orders_sample.csv fixture."""

import pytest

from app.config import Settings
from app.ingestion import service as ingestion_service
from app.kg.entity_extraction import build_graph
from app.kg.graph_retrieval import retrieve
from tests.conftest import FIXTURES_DIR

ORDERS_SAMPLE = (FIXTURES_DIR / "orders_sample.csv").read_bytes()


@pytest.fixture
def built_dataset(db_session):
    dataset = ingestion_service.ingest_upload(db_session, Settings(), "orders_sample.csv", ORDERS_SAMPLE)
    columns = sorted(dataset.columns, key=lambda c: c.position)
    build_graph(db_session, dataset, columns)
    return dataset


def test_retrieve_finds_a_mentioned_customer_and_its_connections(db_session, built_dataset):
    facts = retrieve(db_session, "What region is Alice Johnson in?", max_facts=5)

    assert len(facts) == 1
    fact = facts[0]
    assert fact.filename == f"Knowledge Graph: {built_dataset.name}"
    assert "Alice Johnson" in fact.content
    assert "North" in fact.content  # Alice Johnson's order is in the North region
    assert fact.score == 1.0


def test_retrieve_finds_a_mentioned_product_and_its_customers(db_session, built_dataset):
    facts = retrieve(db_session, "Tell me about the Standing Desk product.", max_facts=5)

    assert len(facts) == 1
    assert "Bob Smith" in facts[0].content  # the only customer who ordered a Standing Desk


def test_retrieve_returns_empty_list_for_a_question_mentioning_no_known_entity(
    db_session, built_dataset
):
    facts = retrieve(db_session, "What is the boiling point of tungsten in kelvin?", max_facts=5)
    assert facts == []


def test_retrieve_returns_empty_list_when_no_graph_has_been_built_at_all(db_session):
    facts = retrieve(db_session, "What region is Alice Johnson in?", max_facts=5)
    assert facts == []


def test_retrieve_caps_the_number_of_facts_at_max_facts(db_session, built_dataset):
    # Every customer_name in the fixture is a distinct entity; asking about
    # several of them at once should never return more than max_facts.
    question = "Compare Alice Johnson, Bob Smith, Carla Diaz, and David Lee."
    facts = retrieve(db_session, question, max_facts=2)
    assert len(facts) <= 2


def test_retrieve_ranks_are_placeholders_reassigned_by_the_caller(db_session, built_dataset):
    # app/rag/service.py re-numbers rank after merging with vector chunks -
    # graph_retrieval.py itself doesn't need to produce meaningful ranks.
    facts = retrieve(db_session, "What region is Alice Johnson in?", max_facts=5)
    assert all(fact.rank == 0 for fact in facts)
