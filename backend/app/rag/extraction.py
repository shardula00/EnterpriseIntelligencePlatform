"""Safe, per-format text extraction.

Every function here returns a list of `ExtractedSegment`s - the unit that
app/rag/chunking.py splits into chunks. A segment is the smallest piece of
*structural* provenance a format actually offers: one page for PDF, one
heading-delimited section for DOCX/Markdown, the whole file for plain text
(which has no structure to preserve beyond that). Nothing here ever
invents page/section information a format doesn't really have.

Every extractor is wrapped so a malformed/corrupt/unsupported file raises
one of app.rag.errors's specific exceptions rather than an arbitrary
library exception - app/rag/service.py turns those into a FAILED document
status instead of a 500, per Phase 7's "avoid crashing the API" requirement.
"""

import re
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import pypdf
from docx import Document as DocxDocument
from docx.opc.exceptions import PackageNotFoundError
from pypdf.errors import PdfReadError

from app.rag.errors import EmptyDocumentError, ExtractionError, UnsupportedDocumentTypeError

_EXTENSION_TO_TYPE = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".txt": "txt",
    ".md": "markdown",
    ".markdown": "markdown",
}


def document_type_from_filename(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in _EXTENSION_TO_TYPE:
        supported = ", ".join(sorted(set(_EXTENSION_TO_TYPE)))
        raise UnsupportedDocumentTypeError(
            f"'{ext or filename}' is not a supported document type. Supported: {supported}."
        )
    return _EXTENSION_TO_TYPE[ext]


@dataclass
class ExtractedSegment:
    """One structural unit of extracted text, before chunking."""

    page_number: int | None
    section_title: str | None
    text: str


def _normalize_whitespace(text: str) -> str:
    """Collapse runs of blank lines/spaces without altering real content -
    extracted PDF/DOCX text often has irregular spacing that would
    otherwise make chunk boundaries look worse than the source material."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_pdf(content: bytes) -> list[ExtractedSegment]:
    try:
        reader = pypdf.PdfReader(BytesIO(content))
        pages = reader.pages
    except (PdfReadError, ValueError, OSError) as exc:
        raise ExtractionError(f"Could not read PDF: {exc}") from exc

    segments: list[ExtractedSegment] = []
    for i, page in enumerate(pages):
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # pypdf can raise many internal error types
            raise ExtractionError(f"Could not extract text from PDF page {i + 1}: {exc}") from exc
        text = _normalize_whitespace(text)
        if text:
            segments.append(ExtractedSegment(page_number=i + 1, section_title=None, text=text))
    return segments


# python-docx treats any paragraph style name starting with "Heading" as a
# section title (e.g. "Heading 1", "Heading 2") - the standard Word
# convention, not something specific to this project's documents.
_HEADING_STYLE_PREFIX = "Heading"


def _extract_docx(content: bytes) -> list[ExtractedSegment]:
    try:
        doc = DocxDocument(BytesIO(content))
    except (PackageNotFoundError, KeyError, ValueError, zipfile.BadZipFile) as exc:
        raise ExtractionError(f"Could not read DOCX: {exc}") from exc

    segments: list[ExtractedSegment] = []
    current_title: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        text = _normalize_whitespace("\n".join(buffer))
        if text:
            segments.append(
                ExtractedSegment(page_number=None, section_title=current_title, text=text)
            )

    for paragraph in doc.paragraphs:
        style_name = paragraph.style.name if paragraph.style else ""
        if style_name.startswith(_HEADING_STYLE_PREFIX):
            flush()
            buffer = []
            current_title = paragraph.text.strip() or None
        elif paragraph.text.strip():
            buffer.append(paragraph.text)
    flush()
    return segments


def _extract_txt(content: bytes) -> list[ExtractedSegment]:
    text = _decode_text(content)
    text = _normalize_whitespace(text)
    if not text:
        return []
    return [ExtractedSegment(page_number=None, section_title=None, text=text)]


_MARKDOWN_HEADING = re.compile(r"^#{1,6}\s+(.*)$")


def _extract_markdown(content: bytes) -> list[ExtractedSegment]:
    text = _decode_text(content)
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    segments: list[ExtractedSegment] = []
    current_title: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        body = _normalize_whitespace("\n".join(buffer))
        if body:
            segments.append(
                ExtractedSegment(page_number=None, section_title=current_title, text=body)
            )

    for line in lines:
        match = _MARKDOWN_HEADING.match(line)
        if match:
            flush()
            buffer = []
            current_title = match.group(1).strip() or None
        else:
            buffer.append(line)
    flush()
    return segments


def _decode_text(content: bytes) -> str:
    """Best-effort decode - never raises on bad encoding. Most enterprise
    text/Markdown files are UTF-8; a Latin-1 fallback never raises (every
    byte sequence is valid Latin-1), so this always returns *something*
    rather than crashing on a mis-encoded file."""
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("latin-1")


_EXTRACTORS = {
    "pdf": _extract_pdf,
    "docx": _extract_docx,
    "txt": _extract_txt,
    "markdown": _extract_markdown,
}


def extract(document_type: str, content: bytes) -> list[ExtractedSegment]:
    """Extract structured text segments from raw file bytes.

    Raises EmptyDocumentError if the file is zero-length or every segment's
    text is empty after extraction/normalization (e.g. a scanned PDF with
    no OCR text layer) - a real, expected outcome this project cannot fix
    without adding OCR, not a bug to hide.
    """
    if not content:
        raise EmptyDocumentError("The uploaded file is empty.")
    if document_type not in _EXTRACTORS:
        raise UnsupportedDocumentTypeError(f"'{document_type}' is not a supported document type.")

    segments = _EXTRACTORS[document_type](content)
    if not segments:
        raise EmptyDocumentError(
            "No extractable text was found in this document (it may be empty, "
            "image-only/scanned with no text layer, or contain only formatting)."
        )
    return segments
