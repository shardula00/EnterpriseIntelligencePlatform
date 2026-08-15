"""Tests for app/rag/service.py against a real Postgres (db_session), never
the HTTP layer (that's tests/test_documents_api.py and tests/test_rag_api.py)."""

import pytest
from sqlalchemy.orm import Session

from app.config import Settings
from app.ingestion import service as ingestion_service
from app.kg.service import build_graph_for_dataset
from app.rag import service
from app.rag.embeddings import HashingEmbeddingProvider
from app.rag.errors import (
    DocumentNotFoundError,
    DocumentTooLargeError,
    EmptyDocumentError,
    RagQueryNotFoundError,
    UnsupportedDocumentTypeError,
)
from app.rag.llm import LocalExtractiveProvider
from tests.conftest import FIXTURES_DIR, _create_user_with_role

VACATION_POLICY = (FIXTURES_DIR / "rag" / "employee_handbook_policies.txt").read_bytes()
ORDERS_SAMPLE = (FIXTURES_DIR / "orders_sample.csv").read_bytes()


@pytest.fixture
def settings():
    # A fresh Settings() per test, not the process-wide get_settings()
    # cache - some tests below (e.g. the oversized-file one) deliberately
    # override a field, and mutating the shared cached singleton would
    # leak into every other test in the process.
    return Settings()


@pytest.fixture
def embedding_provider(settings):
    return HashingEmbeddingProvider(settings.rag_embedding_dimension)


@pytest.fixture
def llm_provider():
    return LocalExtractiveProvider()


@pytest.fixture
def user_a(db_session: Session):
    return _create_user_with_role(db_session, "ANALYST")


@pytest.fixture
def user_b(db_session: Session):
    return _create_user_with_role(db_session, "ANALYST")


def _upload(db_session, settings, user, filename="handbook.txt", content=VACATION_POLICY):
    return service.upload_document(db_session, settings, filename, content, user.id)


def _process(db_session, settings, embedding_provider, document, user):
    return service.process_document(db_session, settings, embedding_provider, document.id, user)


def _upload_and_process(db_session, settings, embedding_provider, user, content=VACATION_POLICY):
    document = _upload(db_session, settings, user, content=content)
    return _process(db_session, settings, embedding_provider, document, user)


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


def test_upload_document_starts_in_uploaded_status(db_session, settings, user_a):
    document = _upload(db_session, settings, user_a)
    assert document.status == "uploaded"
    assert document.document_type == "txt"
    assert document.chunk_count == 0
    assert document.uploaded_by == user_a.id
    assert len(document.checksum) == 64


def test_upload_document_rejects_unsupported_extension(db_session, settings, user_a):
    with pytest.raises(UnsupportedDocumentTypeError):
        service.upload_document(db_session, settings, "malware.exe", b"whatever", user_a.id)


def test_upload_document_rejects_empty_file(db_session, settings, user_a):
    with pytest.raises(EmptyDocumentError):
        service.upload_document(db_session, settings, "empty.txt", b"", user_a.id)


def test_upload_document_rejects_oversized_file(db_session, settings, user_a):
    settings.rag_max_upload_size_mb = 0  # any non-empty content now exceeds it
    with pytest.raises(DocumentTooLargeError):
        _upload(db_session, settings, user_a)


# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------


def test_process_document_produces_ready_status_with_chunks(
    db_session, settings, embedding_provider, user_a
):
    document = _upload_and_process(db_session, settings, embedding_provider, user_a)
    assert document.status == "ready"
    assert document.chunk_count > 0
    assert document.error_message is None
    assert len(document.chunks) == document.chunk_count
    assert all(c.embedding_model == embedding_provider.name for c in document.chunks)


def test_process_document_handles_a_corrupt_pdf_without_crashing(
    db_session, settings, embedding_provider, user_a
):
    document = _upload(db_session, settings, user_a, "broken.pdf", b"%PDF-1.4 not a real pdf")
    result = _process(db_session, settings, embedding_provider, document, user_a)
    assert result.status == "failed"
    assert result.error_message is not None
    assert result.chunk_count == 0


def test_process_document_can_be_retried_and_replaces_previous_chunks(
    db_session, settings, embedding_provider, user_a
):
    document = _upload_and_process(db_session, settings, embedding_provider, user_a)
    first_chunk_count = document.chunk_count

    retried = _process(db_session, settings, embedding_provider, document, user_a)
    assert retried.status == "ready"
    assert retried.chunk_count == first_chunk_count  # same input -> same output, not doubled


# ---------------------------------------------------------------------------
# Access control - Phase 7 §11
# ---------------------------------------------------------------------------


def test_get_document_raises_not_found_for_unknown_id(db_session, user_a):
    import uuid

    with pytest.raises(DocumentNotFoundError):
        service.get_document(db_session, uuid.uuid4(), user_a)


def test_get_document_denies_a_non_owner_non_admin_user(db_session, settings, user_a, user_b):
    document = _upload(db_session, settings, user_a)
    with pytest.raises(DocumentNotFoundError):
        service.get_document(db_session, document.id, user_b)


def test_get_document_allows_admin_regardless_of_owner(db_session, settings, user_a):
    admin = _create_user_with_role(db_session, "ADMIN")
    document = _upload(db_session, settings, user_a)
    fetched = service.get_document(db_session, document.id, admin)
    assert fetched.id == document.id


def test_list_documents_shows_only_own_documents_for_a_non_admin(
    db_session, settings, user_a, user_b
):
    doc_a = _upload(db_session, settings, user_a, "a.txt")
    _upload(db_session, settings, user_b, "b.txt")

    listed = service.list_documents(db_session, user_a)
    assert [d.id for d in listed] == [doc_a.id]


def test_list_documents_shows_everything_for_admin(db_session, settings, user_a, user_b):
    doc_a = _upload(db_session, settings, user_a, "a.txt")
    doc_b = _upload(db_session, settings, user_b, "b.txt")
    admin = _create_user_with_role(db_session, "ADMIN")

    listed_ids = {d.id for d in service.list_documents(db_session, admin)}
    assert {doc_a.id, doc_b.id} <= listed_ids


def test_delete_document_denies_a_non_owner_non_admin_user(db_session, settings, user_a, user_b):
    document = _upload(db_session, settings, user_a)
    with pytest.raises(DocumentNotFoundError):
        service.delete_document(db_session, settings, document.id, user_b)


def test_delete_document_removes_the_row(db_session, settings, user_a):
    document = _upload(db_session, settings, user_a)
    service.delete_document(db_session, settings, document.id, user_a)
    with pytest.raises(DocumentNotFoundError):
        service.get_document(db_session, document.id, user_a)


# ---------------------------------------------------------------------------
# RAG query
# ---------------------------------------------------------------------------


def test_run_query_returns_answered_with_sources_for_a_supported_question(
    db_session, settings, embedding_provider, llm_provider, user_a
):
    _upload_and_process(db_session, settings, embedding_provider, user_a)
    query = service.run_query(
        db_session, settings, embedding_provider, llm_provider, user_a,
        "How many vacation days do employees get?",
    )
    assert query.status == "answered"
    assert len(query.sources) > 0
    assert "20" in query.answer
    assert query.sources[0]["filename"] == "handbook.txt"


def test_run_query_returns_insufficient_evidence_for_an_unrelated_question(
    db_session, settings, embedding_provider, llm_provider, user_a
):
    _upload_and_process(db_session, settings, embedding_provider, user_a)
    query = service.run_query(
        db_session, settings, embedding_provider, llm_provider, user_a,
        "What is the boiling point of tungsten in kelvin?",
    )
    assert query.status == "insufficient_evidence"
    assert query.sources == []


def test_run_query_returns_insufficient_evidence_when_the_user_has_no_documents(
    db_session, settings, embedding_provider, llm_provider, user_a
):
    query = service.run_query(
        db_session, settings, embedding_provider, llm_provider, user_a, "Any question at all?",
    )
    assert query.status == "insufficient_evidence"
    assert query.sources == []


def test_run_query_never_retrieves_another_users_document(
    db_session, settings, embedding_provider, llm_provider, user_a, user_b
):
    _upload_and_process(db_session, settings, embedding_provider, user_a)
    query = service.run_query(
        db_session, settings, embedding_provider, llm_provider, user_b,
        "How many vacation days do employees get?",
    )
    assert query.status == "insufficient_evidence"
    assert query.sources == []


def test_run_query_with_explicit_document_ids_for_another_users_document_still_finds_nothing(
    db_session, settings, embedding_provider, llm_provider, user_a, user_b
):
    document = _upload_and_process(db_session, settings, embedding_provider, user_a)
    query = service.run_query(
        db_session, settings, embedding_provider, llm_provider, user_b,
        "How many vacation days do employees get?",
        document_ids=[document.id],
    )
    assert query.status == "insufficient_evidence"
    assert query.sources == []


def test_run_query_persists_a_queryable_rag_query_row(
    db_session, settings, embedding_provider, llm_provider, user_a
):
    _upload_and_process(db_session, settings, embedding_provider, user_a)
    query = service.run_query(
        db_session, settings, embedding_provider, llm_provider, user_a,
        "How many vacation days do employees get?",
    )
    fetched = service.get_query(db_session, query.id, user_a)
    assert fetched.id == query.id
    assert fetched.question == "How many vacation days do employees get?"


def test_get_query_denies_a_non_owner_non_admin_user(
    db_session, settings, embedding_provider, llm_provider, user_a, user_b
):
    _upload_and_process(db_session, settings, embedding_provider, user_a)
    query = service.run_query(
        db_session, settings, embedding_provider, llm_provider, user_a,
        "How many vacation days do employees get?",
    )
    with pytest.raises(RagQueryNotFoundError):
        service.get_query(db_session, query.id, user_b)


def test_list_queries_filters_to_own_for_a_non_admin(
    db_session, settings, embedding_provider, llm_provider, user_a, user_b
):
    _upload_and_process(db_session, settings, embedding_provider, user_a)
    service.run_query(db_session, settings, embedding_provider, llm_provider, user_a, "q1")
    service.run_query(db_session, settings, embedding_provider, llm_provider, user_b, "q2")

    listed = service.list_queries(db_session, user_a)
    assert all(q.asked_by == user_a.id for q in listed)


# ---------------------------------------------------------------------------
# Phase 9: hybrid retrieval_mode - vector-only preserved exactly, hybrid
# only ever *adds* knowledge-graph evidence on top of it.
# ---------------------------------------------------------------------------


def _build_dataset_and_graph(db_session):
    dataset = ingestion_service.ingest_upload(db_session, Settings(), "orders_sample.csv", ORDERS_SAMPLE)
    build_graph_for_dataset(db_session, dataset.id)
    return dataset


def test_default_retrieval_mode_is_vector_only():
    assert Settings().retrieval_mode == "vector_only"


def test_vector_only_mode_cannot_answer_a_graph_only_question(
    db_session, settings, embedding_provider, llm_provider, user_a
):
    # No RAG documents uploaded at all - only a dataset+graph exist. A fact
    # that lives only in structured data must stay unanswerable in
    # vector-only mode, exactly like before Phase 9 existed.
    _build_dataset_and_graph(db_session)
    settings.retrieval_mode = "vector_only"

    query = service.run_query(
        db_session, settings, embedding_provider, llm_provider, user_a,
        "What region is Alice Johnson in?",
    )
    assert query.status == "insufficient_evidence"
    assert query.sources == []


def test_hybrid_mode_answers_the_same_graph_only_question_using_the_knowledge_graph(
    db_session, settings, embedding_provider, llm_provider, user_a
):
    _build_dataset_and_graph(db_session)
    settings.retrieval_mode = "hybrid"

    query = service.run_query(
        db_session, settings, embedding_provider, llm_provider, user_a,
        "What region is Alice Johnson in?",
    )
    assert query.status == "answered"
    assert len(query.sources) == 1
    assert query.sources[0]["filename"].startswith("Knowledge Graph:")
    assert "North" in query.answer  # Alice Johnson's order is in the North region


def test_hybrid_mode_still_answers_from_documents_when_available(
    db_session, settings, embedding_provider, llm_provider, user_a
):
    # Regression: hybrid mode must not interfere with document-grounded
    # answers - it only adds graph evidence, never replaces vector
    # retrieval or changes citations for a purely document-answerable
    # question.
    _upload_and_process(db_session, settings, embedding_provider, user_a)
    settings.retrieval_mode = "hybrid"

    query = service.run_query(
        db_session, settings, embedding_provider, llm_provider, user_a,
        "How many vacation days do employees get?",
    )
    assert query.status == "answered"
    assert "20" in query.answer
    assert query.sources[0]["filename"] == "handbook.txt"


def test_hybrid_mode_combines_document_and_graph_evidence_for_one_query(
    db_session, settings, embedding_provider, llm_provider, user_a
):
    _upload_and_process(db_session, settings, embedding_provider, user_a)
    _build_dataset_and_graph(db_session)
    settings.retrieval_mode = "hybrid"

    query = service.run_query(
        db_session, settings, embedding_provider, llm_provider, user_a,
        "How many vacation days do employees get, and what region is Alice Johnson in?",
    )
    assert query.status == "answered"
    filenames = {s["filename"] for s in query.sources}
    assert "handbook.txt" in filenames
    assert any(f.startswith("Knowledge Graph:") for f in filenames)


def test_hybrid_mode_falls_back_to_insufficient_evidence_when_neither_source_has_an_answer(
    db_session, settings, embedding_provider, llm_provider, user_a
):
    settings.retrieval_mode = "hybrid"
    query = service.run_query(
        db_session, settings, embedding_provider, llm_provider, user_a,
        "What is the boiling point of tungsten in kelvin?",
    )
    assert query.status == "insufficient_evidence"
    assert query.sources == []
