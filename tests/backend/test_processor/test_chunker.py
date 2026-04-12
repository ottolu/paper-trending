from backend.processor.chunker import chunk_text


def test_short_text_single_chunk():
    text = "This is a short paragraph."
    chunks = chunk_text(text, max_chars=1000)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_long_text_splits_by_paragraph():
    paragraphs = ["Paragraph one. " * 20, "Paragraph two. " * 20, "Paragraph three. " * 20]
    text = "\n\n".join(paragraphs)
    chunks = chunk_text(text, max_chars=400)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert len(chunk) <= 400 + 50


def test_empty_text_returns_empty():
    assert chunk_text("", max_chars=1000) == []


def test_respects_overlap():
    text = "A. " * 100 + "\n\n" + "B. " * 100
    chunks = chunk_text(text, max_chars=200, overlap_chars=50)
    assert len(chunks) >= 2


def test_chunks_have_metadata():
    text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    chunks = chunk_text(text, max_chars=30, return_with_metadata=True)
    assert len(chunks) >= 2
    assert all(isinstance(c, dict) for c in chunks)
    assert all("text" in c and "index" in c for c in chunks)
