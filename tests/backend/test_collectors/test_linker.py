from datetime import date

from backend.collectors.linker import PaperLinker
from backend.collectors.raw_paper import RawPaper


def _arxiv_paper(arxiv_id: str, title: str) -> RawPaper:
    return RawPaper(
        source="arxiv",
        source_record_id=arxiv_id,
        arxiv_id=arxiv_id,
        title=title,
        abstract=f"Abstract for {title}",
        authors=["Author A"],
        arxiv_categories=["cs.CL"],
        published_date=date(2024, 1, 15),
        pdf_url=f"http://arxiv.org/pdf/{arxiv_id}",
        source_url=f"http://arxiv.org/abs/{arxiv_id}",
    )


def _hf_paper(arxiv_id: str, title: str, likes: int = 10) -> RawPaper:
    return RawPaper(
        source="huggingface",
        source_record_id=arxiv_id,
        arxiv_id=arxiv_id,
        title=title,
        abstract=f"Abstract for {title}",
        source_url=f"https://huggingface.co/papers/{arxiv_id}",
        hf_likes=likes,
        hf_discussions=2,
    )


def test_link_by_arxiv_id():
    linker = PaperLinker()
    arxiv_papers = [_arxiv_paper("2401.00001", "Paper One")]
    hf_papers = [_hf_paper("2401.00001", "Paper One", likes=42)]

    linked = linker.link(arxiv_papers, hf_papers)

    assert len(linked) == 1
    lp = linked[0]
    assert lp.paper_id == "2401.00001"
    assert lp.arxiv_source is not None
    assert lp.hf_source is not None
    assert lp.match_strategy == "arxiv_id"
    assert lp.match_confidence == 1.0


def test_unmatched_papers_preserved():
    linker = PaperLinker()
    arxiv_papers = [_arxiv_paper("2401.00001", "Paper One")]
    hf_papers = [_hf_paper("2401.99999", "Totally Different Paper")]

    linked = linker.link(arxiv_papers, hf_papers)

    assert len(linked) == 2
    arxiv_only = [lp for lp in linked if lp.hf_source is None]
    hf_only = [lp for lp in linked if lp.arxiv_source is None]
    assert len(arxiv_only) == 1
    assert len(hf_only) == 1


def test_fuzzy_title_match():
    linker = PaperLinker(fuzzy_threshold=0.85)
    arxiv_papers = [_arxiv_paper("2401.00001", "Scaling Laws for Neural Language Models")]
    hf_papers = [
        RawPaper(
            source="huggingface",
            source_record_id="hf-unknown",
            arxiv_id=None,
            title="Scaling Laws for Neural Language Model",
            abstract="Close title match.",
            hf_likes=5,
            hf_discussions=1,
        ),
    ]

    linked = linker.link(arxiv_papers, hf_papers)

    assert len(linked) == 1
    assert linked[0].match_strategy == "fuzzy_title"
    assert linked[0].match_confidence is not None
    assert linked[0].match_confidence >= 0.85


def test_fuzzy_match_below_threshold_not_linked():
    linker = PaperLinker(fuzzy_threshold=0.85)
    arxiv_papers = [_arxiv_paper("2401.00001", "Scaling Laws for Neural Language Models")]
    hf_papers = [
        RawPaper(
            source="huggingface",
            source_record_id="hf-unknown",
            arxiv_id=None,
            title="Completely Unrelated Title About Robots",
            abstract="No match.",
            hf_likes=5,
            hf_discussions=1,
        ),
    ]

    linked = linker.link(arxiv_papers, hf_papers)

    assert len(linked) == 2


def test_linked_paper_primary_fields():
    linker = PaperLinker()
    arxiv_papers = [_arxiv_paper("2401.00001", "Paper One")]
    hf_papers = [_hf_paper("2401.00001", "Paper One", likes=42)]

    linked = linker.link(arxiv_papers, hf_papers)

    lp = linked[0]
    assert lp.title == "Paper One"
    assert lp.abstract == "Abstract for Paper One"
    assert lp.authors == ["Author A"]
    assert lp.arxiv_categories == ["cs.CL"]
    assert lp.published_date == date(2024, 1, 15)
    assert lp.pdf_url == "http://arxiv.org/pdf/2401.00001"


def test_empty_inputs():
    linker = PaperLinker()
    assert linker.link([], []) == []
    assert len(linker.link([_arxiv_paper("2401.00001", "P1")], [])) == 1
    assert len(linker.link([], [_hf_paper("2401.00001", "P1")])) == 1
