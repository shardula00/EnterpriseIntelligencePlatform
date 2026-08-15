"""Deterministic, provenance-preserving chunking.

Splits each ExtractedSegment's text into overlapping windows around
Settings.rag_chunk_size_chars, preferring to break at a paragraph or
sentence boundary near the target size rather than mid-word/mid-sentence,
so a chunk reads as a coherent unit rather than an arbitrary character
slice. Character-based, not token-based (see app/config.py's rationale).

Deterministic by construction: same input text + same size/overlap always
produces the same chunks, in the same order, every time - no randomness,
no model calls. Each chunk keeps its source segment's page_number/
section_title, plus its own start_char/end_char offset within that
segment's text - "document -> page/section -> chunk" provenance, never a
blind split that loses where the text came from.
"""

from dataclasses import dataclass

from app.rag.extraction import ExtractedSegment

# How far back from the ideal cut point we'll look for a clean break
# (paragraph, then sentence, then word boundary) before giving up and
# cutting exactly at the ideal point. A fraction of chunk_size, not a fixed
# count, so it scales sensibly with whatever chunk size is configured.
_BREAK_SEARCH_FRACTION = 0.2


@dataclass
class Chunk:
    chunk_index: int
    content: str
    char_count: int
    page_number: int | None
    section_title: str | None
    start_char: int | None
    end_char: int | None


def _find_break_point(text: str, ideal_end: int, min_end: int) -> int:
    """Search backward from ideal_end (down to min_end) for the best
    available break: a paragraph break, then a sentence end, then a plain
    space. Falls back to ideal_end itself (a hard cut) if none is found -
    always returns a valid index, never fails."""
    window = text[min_end:ideal_end]
    for marker in ("\n\n", ". ", "\n", " "):
        pos = window.rfind(marker)
        if pos != -1:
            return min_end + pos + len(marker)
    return ideal_end


def _split_text(text: str, chunk_size: int, overlap: int) -> list[tuple[str, int, int]]:
    """Returns [(content, start_char, end_char), ...] for one segment's text."""
    length = len(text)
    if length <= chunk_size:
        return [(text, 0, length)]

    search_window = max(1, int(chunk_size * _BREAK_SEARCH_FRACTION))
    pieces: list[tuple[str, int, int]] = []
    start = 0
    while start < length:
        ideal_end = min(start + chunk_size, length)
        if ideal_end < length:
            min_end = max(start + 1, ideal_end - search_window)
            end = _find_break_point(text, ideal_end, min_end)
        else:
            end = length
        content = text[start:end].strip()
        if content:
            pieces.append((content, start, end))
        if end >= length:
            break
        # Advance by at least one character past the overlap point so a
        # degenerate case (overlap >= chunk length) can never loop forever.
        start = max(end - overlap, start + 1)
    return pieces


def chunk_segments(
    segments: list[ExtractedSegment], chunk_size: int, overlap: int
) -> list[Chunk]:
    """Chunk every segment independently (never merges across a page/
    section boundary, so provenance always points at exactly one page or
    section) and assigns a single sequential chunk_index across the whole
    document, in reading order."""
    chunks: list[Chunk] = []
    index = 0
    for segment in segments:
        for content, start_char, end_char in _split_text(segment.text, chunk_size, overlap):
            chunks.append(
                Chunk(
                    chunk_index=index,
                    content=content,
                    char_count=len(content),
                    page_number=segment.page_number,
                    section_title=segment.section_title,
                    start_char=start_char,
                    end_char=end_char,
                )
            )
            index += 1
    return chunks
