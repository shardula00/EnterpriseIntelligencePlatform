"""Exceptions raised by the ingestion pipeline.

Kept separate from FastAPI so the pipeline stages (parsers, type inference,
etc.) stay framework-agnostic and unit-testable without an app context.
The API layer (app/api/datasets.py) is responsible for translating these
into HTTP responses.
"""


class IngestionError(Exception):
    """Base class for all ingestion pipeline failures."""


class UnsupportedFileTypeError(IngestionError):
    """Raised when a file's extension/content-type isn't CSV, XLSX, or JSON."""


class FileTooLargeError(IngestionError):
    """Raised when an upload exceeds Settings.max_upload_size_mb."""


class EmptyFileError(IngestionError):
    """Raised when a file has no data (zero bytes, zero rows, or zero columns)."""


class ParseError(IngestionError):
    """Raised when a file cannot be parsed as its declared format."""


class DatasetNotFoundError(IngestionError):
    """Raised when a dataset id doesn't exist."""
