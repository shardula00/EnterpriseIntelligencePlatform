"""Exceptions raised by the RAG package."""


class RagError(Exception):
    """Base class for all RAG failures."""


class DocumentNotFoundError(RagError):
    """Raised when a document id doesn't exist, OR exists but the current
    user isn't its uploader/an ADMIN. Deliberately the same error/message
    for both cases (see app/rag/service.py's _ensure_access) - "not found"
    doesn't confirm or deny that another user's document exists."""


class UnsupportedDocumentTypeError(RagError):
    """Raised when a file's extension isn't PDF, DOCX, TXT, or Markdown."""


class DocumentTooLargeError(RagError):
    """Raised when an upload exceeds Settings.rag_max_upload_size_mb."""


class EmptyDocumentError(RagError):
    """Raised when a file has zero bytes, or extracted text is empty/whitespace."""


class ExtractionError(RagError):
    """Raised when a file cannot be parsed as its declared format (e.g. a
    corrupt/malformed PDF) - caught and turned into a FAILED document
    status by the caller, never left to crash the API."""


class LLMProviderError(RagError):
    """Raised by an LLMProvider when generation itself fails (provider
    unreachable, misconfigured, bad response) - distinct from
    "insufficient evidence": this means the system couldn't even attempt
    an answer, not that it correctly declined to fabricate one. Caught by
    app/rag/service.py and turned into a QueryStatus="error" result, never
    left to crash the API."""


class RagQueryNotFoundError(RagError):
    """Raised when a rag_queries id doesn't exist, or doesn't belong to the
    current user (see DocumentNotFoundError - same non-disclosure reasoning)."""
