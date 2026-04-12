from __future__ import annotations

import difflib
from dataclasses import dataclass
from datetime import date

from backend.collectors.raw_paper import RawPaper


@dataclass
class LinkedPaper:
    """A paper with merged data from arXiv and/or HuggingFace sources."""

    paper_id: str
    title: str
    authors: list[str]
    abstract: str
    arxiv_id: str | None
    arxiv_categories: list[str]
    published_date: date | None
    pdf_url: str | None
    arxiv_source: RawPaper | None
    hf_source: RawPaper | None
    match_strategy: str  # "arxiv_id", "fuzzy_title", or "none"
    match_confidence: float | None


class PaperLinker:
    def __init__(self, fuzzy_threshold: float = 0.85):
        self._fuzzy_threshold = fuzzy_threshold

    def link(
        self,
        arxiv_papers: list[RawPaper],
        hf_papers: list[RawPaper],
    ) -> list[LinkedPaper]:
        results: list[LinkedPaper] = []
        hf_by_arxiv_id: dict[str, RawPaper] = {}
        hf_unmatched: list[RawPaper] = []

        for hf in hf_papers:
            if hf.arxiv_id:
                hf_by_arxiv_id[hf.arxiv_id] = hf
            else:
                hf_unmatched.append(hf)

        matched_hf_ids: set[str] = set()

        for arxiv in arxiv_papers:
            hf_match: RawPaper | None = None
            strategy = "none"
            confidence: float | None = None

            if arxiv.arxiv_id and arxiv.arxiv_id in hf_by_arxiv_id:
                hf_match = hf_by_arxiv_id[arxiv.arxiv_id]
                strategy = "arxiv_id"
                confidence = 1.0
                matched_hf_ids.add(arxiv.arxiv_id)
            else:
                best_ratio = 0.0
                best_hf: RawPaper | None = None
                for hf in hf_unmatched:
                    ratio = difflib.SequenceMatcher(
                        None,
                        arxiv.title.lower(),
                        hf.title.lower(),
                    ).ratio()
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_hf = hf
                if best_hf and best_ratio >= self._fuzzy_threshold:
                    hf_match = best_hf
                    strategy = "fuzzy_title"
                    confidence = best_ratio
                    hf_unmatched.remove(best_hf)

            results.append(
                LinkedPaper(
                    paper_id=arxiv.arxiv_id or arxiv.source_record_id,
                    title=arxiv.title,
                    authors=arxiv.authors,
                    abstract=arxiv.abstract,
                    arxiv_id=arxiv.arxiv_id,
                    arxiv_categories=arxiv.arxiv_categories,
                    published_date=arxiv.published_date,
                    pdf_url=arxiv.pdf_url,
                    arxiv_source=arxiv,
                    hf_source=hf_match,
                    match_strategy=strategy,
                    match_confidence=confidence,
                )
            )

        for hf_id, hf in hf_by_arxiv_id.items():
            if hf_id not in matched_hf_ids:
                results.append(
                    LinkedPaper(
                        paper_id=hf.arxiv_id or hf.source_record_id,
                        title=hf.title,
                        authors=hf.authors,
                        abstract=hf.abstract,
                        arxiv_id=hf.arxiv_id,
                        arxiv_categories=[],
                        published_date=hf.published_date,
                        pdf_url=None,
                        arxiv_source=None,
                        hf_source=hf,
                        match_strategy="none",
                        match_confidence=None,
                    )
                )

        for hf in hf_unmatched:
            results.append(
                LinkedPaper(
                    paper_id=hf.arxiv_id or hf.source_record_id,
                    title=hf.title,
                    authors=hf.authors,
                    abstract=hf.abstract,
                    arxiv_id=hf.arxiv_id,
                    arxiv_categories=[],
                    published_date=hf.published_date,
                    pdf_url=None,
                    arxiv_source=None,
                    hf_source=hf,
                    match_strategy="none",
                    match_confidence=None,
                )
            )

        return results
