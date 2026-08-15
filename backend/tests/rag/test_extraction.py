"""Unit tests for app/rag/extraction.py - no database, no network."""

import pytest

from app.rag import extraction
from app.rag.errors import EmptyDocumentError, ExtractionError, UnsupportedDocumentTypeError
from tests.conftest import FIXTURES_DIR

RAG_FIXTURES = FIXTURES_DIR / "rag"


def test_document_type_from_filename_covers_every_supported_extension():
    assert extraction.document_type_from_filename("a.pdf") == "pdf"
    assert extraction.document_type_from_filename("a.docx") == "docx"
    assert extraction.document_type_from_filename("a.txt") == "txt"
    assert extraction.document_type_from_filename("a.md") == "markdown"
    assert extraction.document_type_from_filename("a.markdown") == "markdown"


def test_document_type_from_filename_rejects_unsupported_extension():
    with pytest.raises(UnsupportedDocumentTypeError):
        extraction.document_type_from_filename("a.exe")


def test_extract_raises_for_empty_bytes():
    with pytest.raises(EmptyDocumentError):
        extraction.extract("txt", b"")


def test_extract_txt_produces_one_segment_with_no_page_or_section():
    segments = extraction.extract("txt", b"Hello world.\n\nSecond paragraph.")
    assert len(segments) == 1
    assert segments[0].page_number is None
    assert segments[0].section_title is None
    assert "Hello world." in segments[0].text


def test_extract_txt_falls_back_to_latin1_on_bad_utf8():
    # 0xff is invalid UTF-8 on its own but is a valid Latin-1 byte - this
    # must never raise, per "avoid crashing the API" on malformed input.
    segments = extraction.extract("txt", b"caf\xe9 misc bytes \xff")
    assert len(segments) == 1


def test_extract_txt_raises_empty_document_for_whitespace_only_content():
    with pytest.raises(EmptyDocumentError):
        extraction.extract("txt", b"   \n\n   \t  ")


def test_extract_markdown_splits_on_headings_and_keeps_titles():
    content = b"# Title\n\nIntro text.\n\n## Section A\n\nBody A.\n\n## Section B\n\nBody B.\n"
    segments = extraction.extract("markdown", content)
    titles = [s.section_title for s in segments]
    assert "Title" in titles
    assert "Section A" in titles
    assert "Section B" in titles
    section_a = next(s for s in segments if s.section_title == "Section A")
    assert "Body A" in section_a.text


def test_extract_markdown_preamble_before_first_heading_has_no_title():
    content = b"Preamble text with no heading yet.\n\n# First Heading\n\nBody.\n"
    segments = extraction.extract("markdown", content)
    assert segments[0].section_title is None
    assert "Preamble" in segments[0].text


def test_extract_docx_real_fixture_preserves_section_titles():
    content = (RAG_FIXTURES / "regional_offices.docx").read_bytes()
    segments = extraction.extract("docx", content)
    titles = {s.section_title for s in segments}
    assert "EMEA Region" in titles
    assert "APAC Region" in titles
    assert "Americas Region" in titles
    emea = next(s for s in segments if s.section_title == "EMEA Region")
    assert "London" in emea.text


def test_extract_docx_raises_extraction_error_for_malformed_file():
    with pytest.raises(ExtractionError):
        extraction.extract("docx", b"this is not a real docx file")


def test_extract_pdf_real_fixture_preserves_page_numbers():
    content = (RAG_FIXTURES / "data_retention_policy.pdf").read_bytes()
    segments = extraction.extract("pdf", content)
    assert len(segments) == 2
    assert segments[0].page_number == 1
    assert segments[1].page_number == 2
    assert "7 years" in segments[0].text
    assert "Data Protection Officer" in segments[1].text


def test_extract_pdf_raises_extraction_error_for_malformed_file():
    with pytest.raises(ExtractionError):
        extraction.extract("pdf", b"%PDF-1.4 this is not a valid pdf body")


def test_extract_raises_unsupported_document_type_for_unknown_type():
    with pytest.raises(UnsupportedDocumentTypeError):
        extraction.extract("csv", b"a,b,c\n1,2,3")
