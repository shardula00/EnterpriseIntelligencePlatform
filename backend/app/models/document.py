"""Enterprise document + chunk models (Phase 7 - RAG).

Document mirrors Dataset's shape (id/filename/type/status/created_by/
source_file_path) rather than inventing a parallel pattern; the genuinely
new thing here is `uploaded_by`-based *ownership*, since documents are
treated as private to their uploader (plus ADMIN) rather than shared
organization-wide like datasets are - see app/rag/__init__.py for why.

No separate `document_versions` table: re-uploading a file creates an
independent new Document, exactly like re-uploading a dataset does (Phase
2). `version` exists as a plain integer column (always 1 today) so the
metadata shape the spec asks for is present without building real
multi-version tracking nothing else in this phase needs.

No separate `embedding_metadata` table either: each chunk has exactly one
current embedding, so `embedding_model`/`embedding_dimension` are stored
directly on DocumentChunk rather than normalized into their own table.
"""

import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# UPLOADED: file saved, not yet processed. PROCESSING: extraction/chunking/
# embedding is running (synchronous - see app/rag/__init__.py - so this
# state is real but brief, never a stuck background job). READY: at least
# one chunk was embedded and stored; queryable. FAILED: processing raised
# an error that couldn't be recovered from automatically (see error_message).
DOCUMENT_STATUSES = ("uploaded", "processing", "ready", "failed")

DOCUMENT_TYPES = ("pdf", "docx", "txt", "markdown")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    document_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="uploaded")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)  # sha256 hex
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Path to the retained raw upload, relative to Settings.
    # rag_document_storage_dir - same provenance pattern as Dataset.
    # source_file_path. NULL if the raw file couldn't be retained.
    source_file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Ownership (new in Phase 7 - see module docstring). SET NULL, not
    # CASCADE: a document shouldn't vanish just because the uploader's
    # account was later deleted, matching MLRun.created_by/audit_logs.user_id.
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow, nullable=False)

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index",
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # Provenance (see app/rag/chunking.py). All nullable: a plain .txt file
    # has no pages/sections, so these are honestly absent, not defaulted to
    # a misleading 0/"".
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    start_char: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_char: Mapped[int | None] = mapped_column(Integer, nullable=True)

    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)

    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)

    document: Mapped["Document"] = relationship(back_populates="chunks")


class RagQuery(Base):
    """One row per question asked through POST /rag/query - the richer,
    queryable counterpart to the lightweight `rag.query_performed` audit
    log entry (same MLRun-vs-AuditLog split as Phase 5/6). `sources` is a
    JSONB list of {document_id, chunk_id, filename, page_number,
    section_title, score, rank} dicts - a normalized join table would be
    over-structuring data that's only ever read back as one unit, never
    queried by its individual fields."""

    __tablename__ = "rag_queries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asked_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    # "answered" (grounded answer, >=1 source above threshold), "insufficient_evidence"
    # (retrieval found nothing usable - see app/rag/service.py), "error".
    status: Mapped[str] = mapped_column(String(30), nullable=False)

    llm_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    llm_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sources: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
