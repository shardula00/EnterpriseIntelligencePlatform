"""Orchestration layer for the RAG API - the only module app/api/documents.py
and app/api/rag.py call. Ties together extraction, chunking, embeddings,
retrieval, and LLM generation with Document/DocumentChunk/RagQuery
persistence, and enforces document ownership (see _ensure_access) on every
document-scoped operation, not just at retrieval time.
"""

import hashlib
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.kg.service import retrieve_graph_evidence
from app.models.document import Document, DocumentChunk, RagQuery
from app.models.user import User
from app.rag import chunking, extraction
from app.rag.embeddings import EmbeddingProvider
from app.rag.errors import (
    DocumentNotFoundError,
    DocumentTooLargeError,
    EmptyDocumentError,
    ExtractionError,
    RagQueryNotFoundError,
    UnsupportedDocumentTypeError,
)
from app.rag.llm import INSUFFICIENT_EVIDENCE_MESSAGE, LLMProvider, LLMProviderError
from app.rag.retrieval import RetrievedChunk, is_admin, retrieve

# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _retain_raw_file(
    settings: Settings, document_id: uuid.UUID, filename: str, content: bytes
) -> str | None:
    """Save the original upload for provenance. Best-effort, same pattern
    as app/ingestion/service.py's _retain_raw_file: a failure here degrades
    provenance, it doesn't abort the upload."""
    safe_name = Path(filename).name or "upload"
    storage_filename = f"{document_id.hex}_{safe_name}"
    try:
        settings.rag_document_storage_dir.mkdir(parents=True, exist_ok=True)
        (settings.rag_document_storage_dir / storage_filename).write_bytes(content)
    except OSError:
        return None
    return storage_filename


def upload_document(
    db: Session,
    settings: Settings,
    filename: str,
    content: bytes,
    uploaded_by: uuid.UUID | None,
) -> Document:
    """Validate and save a document. Does NOT extract/chunk/embed - that's
    process_document()'s job, kept as a separate step so "did the file
    arrive safely" and "did we successfully turn it into retrievable
    knowledge" are independently observable states (see
    app/models/document.py's DOCUMENT_STATUSES)."""
    max_bytes = settings.rag_max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise DocumentTooLargeError(
            f"File is {len(content) / (1024 * 1024):.1f}MB, exceeding the "
            f"{settings.rag_max_upload_size_mb}MB upload limit."
        )
    if not content:
        raise EmptyDocumentError("The uploaded file is empty.")

    document_type = extraction.document_type_from_filename(filename)
    document_id = uuid.uuid4()
    source_file_path = _retain_raw_file(settings, document_id, filename, content)

    document = Document(
        id=document_id,
        filename=filename,
        document_type=document_type,
        status="uploaded",
        version=1,
        checksum=_sha256(content),
        file_size_bytes=len(content),
        chunk_count=0,
        source_file_path=source_file_path,
        uploaded_by=uploaded_by,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def _ensure_access(document: Document, user: User) -> None:
    """A document is visible only to its uploader or an ADMIN - see
    app/rag/__init__.py. Raises the *same* DocumentNotFoundError an
    actually-missing id would raise, so a caller can't distinguish
    "doesn't exist" from "exists but isn't yours" - Phase 7 §11."""
    if is_admin(user):
        return
    if document.uploaded_by != user.id:
        raise DocumentNotFoundError(f"Document {document.id} not found.")


def get_document(db: Session, document_id: uuid.UUID, user: User) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise DocumentNotFoundError(f"Document {document_id} not found.")
    _ensure_access(document, user)
    return document


def list_documents(db: Session, user: User, status: str | None = None) -> list[Document]:
    stmt = select(Document).order_by(Document.created_at.desc())
    if not is_admin(user):
        stmt = stmt.where(Document.uploaded_by == user.id)
    if status is not None:
        stmt = stmt.where(Document.status == status)
    return list(db.execute(stmt).scalars())


def _read_raw_file(settings: Settings, document: Document) -> bytes:
    if document.source_file_path is None:
        raise ExtractionError(
            "The original uploaded file could not be found (it may not have "
            "been retained at upload time)."
        )
    path = settings.rag_document_storage_dir / document.source_file_path
    return path.read_bytes()


def process_document(
    db: Session,
    settings: Settings,
    embedding_provider: EmbeddingProvider,
    document_id: uuid.UUID,
    user: User,
) -> Document:
    """Run extract -> chunk -> embed -> store for one document, synchronously
    (see app/rag/__init__.py for why - same tradeoff as Phase 5 training).
    Anticipated failures (malformed file, unsupported type, no extractable
    text) are caught and turned into a FAILED status with a human-readable
    error_message - never a 500. Callable again on a FAILED document to
    retry (e.g. after fixing an underlying issue), replacing any partial
    chunks from the earlier attempt."""
    document = get_document(db, document_id, user)

    document.status = "processing"
    document.error_message = None
    db.commit()

    try:
        raw_bytes = _read_raw_file(settings, document)
        segments = extraction.extract(document.document_type, raw_bytes)
        chunks = chunking.chunk_segments(
            segments, settings.rag_chunk_size_chars, settings.rag_chunk_overlap_chars
        )
        if not chunks:
            raise EmptyDocumentError("No extractable text produced any chunks.")

        embeddings = embedding_provider.embed_documents([c.content for c in chunks])
    except (ExtractionError, EmptyDocumentError, UnsupportedDocumentTypeError) as exc:
        document.status = "failed"
        document.error_message = str(exc)
        db.commit()
        db.refresh(document)
        return document

    # Replace any chunks from a previous (e.g. failed, retried) attempt -
    # cascade-deleted via the relationship, then rebuilt fresh below.
    document.chunks = [
        DocumentChunk(
            document_id=document.id,
            chunk_index=c.chunk_index,
            content=c.content,
            char_count=c.char_count,
            page_number=c.page_number,
            section_title=c.section_title,
            start_char=c.start_char,
            end_char=c.end_char,
            embedding=vector,
            embedding_model=embedding_provider.name,
        )
        for c, vector in zip(chunks, embeddings, strict=True)
    ]
    document.chunk_count = len(chunks)
    document.status = "ready"
    db.commit()
    db.refresh(document)
    return document


def delete_document(db: Session, settings: Settings, document_id: uuid.UUID, user: User) -> None:
    document = get_document(db, document_id, user)
    if document.source_file_path:
        try:
            (settings.rag_document_storage_dir / document.source_file_path).unlink(missing_ok=True)
        except OSError:
            pass  # best-effort, same as ingestion - a stray file is not worth failing the delete
    db.delete(document)
    db.commit()


# ---------------------------------------------------------------------------
# RAG query
# ---------------------------------------------------------------------------


def _to_sources(chunks: list[RetrievedChunk]) -> list[dict]:
    excerpt_len = 240
    return [
        {
            "document_id": str(c.document_id),
            "filename": c.filename,
            "chunk_id": str(c.chunk_id),
            "chunk_index": c.chunk_index,
            "page_number": c.page_number,
            "section_title": c.section_title,
            "rank": c.rank,
            "score": round(c.score, 4),
            "excerpt": c.content[:excerpt_len] + ("…" if len(c.content) > excerpt_len else ""),
        }
        for c in chunks
    ]


def run_query(
    db: Session,
    settings: Settings,
    embedding_provider: EmbeddingProvider,
    llm_provider: LLMProvider,
    user: User,
    question: str,
    document_ids: list[uuid.UUID] | None = None,
    top_k: int | None = None,
) -> RagQuery:
    """The full question -> retrieve -> generate -> cite pipeline. Always
    returns a persisted RagQuery, never raises for a downstream LLM
    failure - that becomes a status="error" result instead, so a flaky
    Ollama/OpenAI endpoint can never surface as a 500 (see QueryStatus).

    Phase 9: when Settings.retrieval_mode == "hybrid", knowledge-graph
    evidence (app/kg/service.py) is appended to the vector-retrieved
    chunks before generation - packaged as the same RetrievedChunk shape,
    so citations/build_prompt() need no special-casing. When
    retrieval_mode == "vector_only" (the default), this branch is never
    entered and behavior is identical to before Phase 9 existed."""
    chunks = retrieve(
        db, settings, embedding_provider, user, question, document_ids=document_ids, top_k=top_k
    )

    if settings.retrieval_mode == "hybrid":
        graph_chunks = retrieve_graph_evidence(db, question, settings.kg_max_facts_per_query)
        if graph_chunks:
            chunks = chunks + graph_chunks
            for rank, chunk in enumerate(chunks, start=1):
                chunk.rank = rank

    if not chunks:
        answer = INSUFFICIENT_EVIDENCE_MESSAGE
        status = "insufficient_evidence"
        llm_model = None
    else:
        try:
            result = llm_provider.generate(question, chunks)
            answer = result.answer
            status = "answered"
            llm_model = result.model_name
        except LLMProviderError:
            answer = (
                "The configured language model provider is currently unavailable. "
                "Please try again later."
            )
            status = "error"
            llm_model = None

    query = RagQuery(
        asked_by=user.id,
        question=question,
        answer=answer,
        status=status,
        llm_provider=llm_provider.name,
        llm_model=llm_model,
        sources=_to_sources(chunks),
    )
    db.add(query)
    db.commit()
    db.refresh(query)
    return query


def _ensure_query_access(query: RagQuery, user: User) -> None:
    if is_admin(user):
        return
    if query.asked_by != user.id:
        raise RagQueryNotFoundError(f"Query {query.id} not found.")


def get_query(db: Session, query_id: uuid.UUID, user: User) -> RagQuery:
    query = db.get(RagQuery, query_id)
    if query is None:
        raise RagQueryNotFoundError(f"Query {query_id} not found.")
    _ensure_query_access(query, user)
    return query


def list_queries(db: Session, user: User, limit: int = 50) -> list[RagQuery]:
    stmt = select(RagQuery).order_by(RagQuery.created_at.desc()).limit(limit)
    if not is_admin(user):
        stmt = stmt.where(RagQuery.asked_by == user.id)
    return list(db.execute(stmt).scalars())
