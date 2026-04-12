from datetime import date

from backend.collectors.raw_paper import RawPaper


def test_raw_paper_creation_minimal():
    paper = RawPaper(
        source="arxiv",
        source_record_id="2401.00001",
        title="Test Paper",
        abstract="This is a test abstract.",
    )
    assert paper.source == "arxiv"
    assert paper.source_record_id == "2401.00001"
    assert paper.title == "Test Paper"
    assert paper.abstract == "This is a test abstract."
    assert paper.arxiv_id is None
    assert paper.authors == []
    assert paper.arxiv_categories == []
    assert paper.published_date is None
    assert paper.pdf_url is None
    assert paper.source_url is None
    assert paper.hf_likes is None
    assert paper.hf_discussions is None


def test_raw_paper_creation_full():
    paper = RawPaper(
        source="arxiv",
        source_record_id="2401.00001",
        arxiv_id="2401.00001",
        title="Full Paper",
        authors=["Author A", "Author B"],
        abstract="Full abstract.",
        arxiv_categories=["cs.CL", "cs.AI"],
        published_date=date(2024, 1, 15),
        pdf_url="https://arxiv.org/pdf/2401.00001",
        source_url="https://arxiv.org/abs/2401.00001",
    )
    assert paper.arxiv_id == "2401.00001"
    assert paper.authors == ["Author A", "Author B"]
    assert paper.arxiv_categories == ["cs.CL", "cs.AI"]
    assert paper.published_date == date(2024, 1, 15)
    assert paper.pdf_url == "https://arxiv.org/pdf/2401.00001"
    assert paper.source_url == "https://arxiv.org/abs/2401.00001"


def test_raw_paper_huggingface_source():
    paper = RawPaper(
        source="huggingface",
        source_record_id="hf-paper-123",
        title="HF Paper",
        abstract="HF abstract.",
        source_url="https://huggingface.co/papers/2401.00001",
        hf_likes=42,
        hf_discussions=5,
        arxiv_id="2401.00001",
    )
    assert paper.source == "huggingface"
    assert paper.hf_likes == 42
    assert paper.hf_discussions == 5
