from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class RawPaper:
    """Common format returned by all source fetchers."""

    source: str  # "arxiv" or "huggingface"
    source_record_id: str
    title: str
    abstract: str
    arxiv_id: str | None = None
    authors: list[str] = field(default_factory=list)
    arxiv_categories: list[str] = field(default_factory=list)
    published_date: date | None = None
    pdf_url: str | None = None
    source_url: str | None = None
    hf_likes: int | None = None
    hf_discussions: int | None = None
