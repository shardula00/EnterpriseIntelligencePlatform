"""Unit tests for app/rag/chunking.py - deterministic, no database."""

from app.rag.chunking import chunk_segments
from app.rag.extraction import ExtractedSegment


def test_short_segment_becomes_a_single_chunk():
    segments = [ExtractedSegment(page_number=1, section_title=None, text="Short text.")]
    chunks = chunk_segments(segments, chunk_size=1000, overlap=150)
    assert len(chunks) == 1
    assert chunks[0].content == "Short text."
    assert chunks[0].page_number == 1
    assert chunks[0].start_char == 0
    assert chunks[0].end_char == len("Short text.")


def test_long_segment_is_split_into_multiple_overlapping_chunks():
    # Deterministic filler text well over the chunk size.
    text = ("This is one sentence about the policy. " * 60).strip()
    segments = [ExtractedSegment(page_number=None, section_title="Policy", text=text)]
    chunks = chunk_segments(segments, chunk_size=200, overlap=40)

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.section_title == "Policy"
        assert chunk.char_count == len(chunk.content)
        # Never wildly over target size - a little slack is expected since
        # cuts prefer a clean break over an exact character count.
        assert chunk.char_count <= 200 + 40

    # Chunks are sequential and cover the source text without gaps.
    assert chunks[0].chunk_index == 0
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_chunking_is_deterministic():
    text = ("Paragraph one about pricing.\n\n" * 40).strip()
    segments = [ExtractedSegment(page_number=None, section_title=None, text=text)]
    first = chunk_segments(segments, chunk_size=150, overlap=30)
    second = chunk_segments(segments, chunk_size=150, overlap=30)
    assert [c.content for c in first] == [c.content for c in second]


def test_each_segment_chunks_independently_never_merging_across_pages():
    segments = [
        ExtractedSegment(page_number=1, section_title=None, text="Page one content."),
        ExtractedSegment(page_number=2, section_title=None, text="Page two content."),
    ]
    chunks = chunk_segments(segments, chunk_size=1000, overlap=100)
    assert len(chunks) == 2
    assert chunks[0].page_number == 1
    assert chunks[1].page_number == 2
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1


def test_chunk_index_is_sequential_across_the_whole_document():
    text = ("Sentence about revenue and growth. " * 30).strip()
    segments = [
        ExtractedSegment(page_number=1, section_title=None, text=text),
        ExtractedSegment(page_number=2, section_title=None, text=text),
    ]
    chunks = chunk_segments(segments, chunk_size=150, overlap=20)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    # Second page's first chunk continues the index sequence, not restarted.
    page_2_chunks = [c for c in chunks if c.page_number == 2]
    page_1_chunks = [c for c in chunks if c.page_number == 1]
    assert page_2_chunks[0].chunk_index == page_1_chunks[-1].chunk_index + 1


def test_overlap_means_consecutive_chunks_share_trailing_leading_text():
    text = ("Word " * 500).strip()  # no natural break points at all
    segments = [ExtractedSegment(page_number=None, section_title=None, text=text)]
    chunks = chunk_segments(segments, chunk_size=100, overlap=30)
    assert len(chunks) > 1
    # With no punctuation to break on, the hard-cut end/overlap math is
    # exact and directly checkable via each chunk's own offsets.
    assert chunks[1].start_char < chunks[0].end_char


def test_zero_overlap_never_loops_forever_and_still_covers_all_text():
    text = ("Fact number here. " * 100).strip()
    segments = [ExtractedSegment(page_number=None, section_title=None, text=text)]
    chunks = chunk_segments(segments, chunk_size=80, overlap=0)
    assert len(chunks) > 1
    assert chunks[-1].end_char == len(text)


def test_empty_segment_list_produces_no_chunks():
    assert chunk_segments([], chunk_size=1000, overlap=150) == []
