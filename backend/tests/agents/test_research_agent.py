"""Tests for app/agents/research_agent.py against a real Postgres."""

import pytest

from app.agents import research_agent
from app.config import Settings
from app.rag import service as rag_service
from tests.conftest import FIXTURES_DIR, _create_user_with_role

VACATION_POLICY = (FIXTURES_DIR / "rag" / "employee_handbook_policies.txt").read_bytes()


@pytest.fixture
def analyst(db_session):
    return _create_user_with_role(db_session, "ANALYST")


def _upload_and_process(db_session, settings, user):
    from app.rag.embeddings import HashingEmbeddingProvider

    document = rag_service.upload_document(db_session, settings, "handbook.txt", VACATION_POLICY, user.id)
    return rag_service.process_document(
        db_session, settings, HashingEmbeddingProvider(settings.rag_embedding_dimension), document.id, user
    )


def test_answer_returns_a_grounded_result_for_a_document_backed_question(db_session, analyst):
    settings = Settings()
    _upload_and_process(db_session, settings, analyst)

    outcome = research_agent.answer(
        db_session, settings, analyst, "How many vacation days do employees get?"
    )
    assert outcome.allowed is True
    assert outcome.data["status"] == "answered"
    assert "20" in outcome.summary


def test_answer_returns_insufficient_evidence_for_an_unrelated_question(db_session, analyst):
    settings = Settings()
    outcome = research_agent.answer(
        db_session, settings, analyst, "What is the boiling point of tungsten in kelvin?"
    )
    assert outcome.allowed is True
    assert outcome.data["status"] == "insufficient_evidence"


def test_answer_denied_without_rag_query_permission(db_session):
    viewer = _create_user_with_role(db_session, "VIEWER")
    outcome = research_agent.answer(db_session, Settings(), viewer, "Any question?")
    assert outcome.allowed is False
