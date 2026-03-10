from app.services.ingestion import ExtractedSegment, chunk_segments, normalize_text


def test_normalize_text_collapses_whitespace():
    assert normalize_text("Line one\n\n   line two\tline three") == "Line one line two line three"


def test_chunk_segments_preserves_overlap_and_page_metadata():
    content = " ".join(f"word{i}" for i in range(0, 900))
    segments = [ExtractedSegment(text=content, page_number=4, section_title="Billing")]

    chunks = chunk_segments(segments, chunk_size_words=400, overlap_words=100)

    assert len(chunks) == 3
    assert chunks[0].page_number == 4
    assert chunks[0].section_title == "Billing"
    assert chunks[1].content.split()[0] == "word300"
