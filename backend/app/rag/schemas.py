"""Pydantic request/response models for the RAG API (app/api/documents.py,
app/api/rag.py)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

DocumentStatus = Literal["uploaded", "processing", "ready", "failed"]
DocumentType = Literal["pdf", "docx", "txt", "markdown"]
QueryStatus = Literal["answered", "insufficient_evidence", "error"]

# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


class DocumentOut(BaseModel):
    id: UUID
    filename: str
    document_type: DocumentType
    status: DocumentStatus
    error_message: str | None
    version: int
    checksum: str
    file_size_bytes: int
    chunk_count: int
    uploaded_by: UUID | None
    created_at: datetime
    updated_at: datetime


class ChunkOut(BaseModel):
    id: UUID
    chunk_index: int
    content: str
    char_count: int
    page_number: int | None
    section_title: str | None


class DocumentDetailOut(DocumentOut):
    chunks: list[ChunkOut] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# RAG query
# ---------------------------------------------------------------------------


class RagQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    document_ids: list[UUID] | None = Field(
        default=None,
        description="Optional: restrict retrieval to these document ids only.",
    )
    top_k: int | None = Field(default=None, ge=1, le=20)


class SourceOut(BaseModel):
    document_id: UUID
    filename: str
    chunk_id: UUID
    chunk_index: int
    page_number: int | None
    section_title: str | None
    rank: int
    score: float
    excerpt: str


class RagQueryOut(BaseModel):
    id: UUID
    question: str
    answer: str
    status: QueryStatus
    sources: list[SourceOut]
    llm_provider: str
    llm_model: str | None
    created_at: datetime


class RagQuerySummaryOut(BaseModel):
    id: UUID
    question: str
    status: QueryStatus
    source_count: int
    created_at: datetime
