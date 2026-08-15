"""Vector similarity search - the only place a RAG question ever touches
document_chunks. Access control is enforced inside the SQL query itself
(see _scope_to_accessible_documents), not by filtering results in Python
after the fact and never left to the frontend - Phase 7's §11 requirement.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.document import Document, DocumentChunk
from app.models.user import User
from app.rag.embeddings import EmbeddingProvider


@dataclass
class RetrievedChunk:
    chunk_id: UUID
    document_id: UUID
    filename: str
    chunk_index: int
    page_number: int | None
    section_title: str | None
    content: str
    score: float
    rank: int


def is_admin(user: User) -> bool:
    return any(role.name == "ADMIN" for role in user.roles)


def _scope_to_accessible_documents(stmt: Select, user: User) -> Select:
    """A document is retrievable by its uploader or by an ADMIN - nobody
    else, regardless of role/permission. This is an ownership check, not a
    permission check (see app/rag/__init__.py); applied here so it's
    impossible to reach document_chunks through retrieval without it."""
    if is_admin(user):
        return stmt
    return stmt.where(Document.uploaded_by == user.id)


def retrieve(
    db: Session,
    settings: Settings,
    embedding_provider: EmbeddingProvider,
    user: User,
    question: str,
    document_ids: list[UUID] | None = None,
    top_k: int | None = None,
) -> list[RetrievedChunk]:
    """Embed the question, run a pgvector cosine-distance search scoped to
    documents the user may access, and return chunks that clear
    Settings.rag_similarity_threshold - ranked, but not yet threshold-
    filtered, so callers can tell "nothing relevant enough" (empty list)
    apart from "found something, just not much" (see app/rag/service.py).
    """
    k = top_k or settings.rag_top_k
    query_vector = embedding_provider.embed_query(question)

    # A query with no distinguishable content words (e.g. all stop words)
    # embeds to a zero vector under the hashing provider - cosine
    # similarity/distance against a zero vector is mathematically
    # undefined (division by a zero norm), which pgvector represents as
    # NaN and Postgres's JSON type then refuses to store. Treat it the
    # same as "nothing relevant enough was found" rather than letting a
    # NaN reach the database - both is the honest outcome anyway: a
    # question with no real content has nothing to match against.
    if not any(query_vector):
        return []

    stmt = (
        select(
            DocumentChunk,
            Document.filename,
            DocumentChunk.embedding.cosine_distance(query_vector).label("distance"),
        )
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(Document.status == "ready")
    )
    stmt = _scope_to_accessible_documents(stmt, user)
    if document_ids:
        stmt = stmt.where(Document.id.in_(document_ids))
    stmt = stmt.order_by("distance").limit(k)

    rows = db.execute(stmt).all()

    results: list[RetrievedChunk] = []
    for rank, (chunk, filename, distance) in enumerate(rows, start=1):
        score = 1.0 - float(distance)
        if score < settings.rag_similarity_threshold:
            continue
        results.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                filename=filename,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                section_title=chunk.section_title,
                content=chunk.content,
                score=score,
                rank=rank,
            )
        )
    return results
