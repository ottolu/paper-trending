from __future__ import annotations

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from datetime import date

import httpx

from backend.collectors.raw_paper import RawPaper

logger = logging.getLogger(__name__)

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM_NS = "http://www.w3.org/2005/Atom"
ARXIV_NS = "http://arxiv.org/schemas/atom"

_ARXIV_ID_RE = re.compile(r"arxiv\.org/abs/(.+?)(?:v\d+)?$")


class ArxivFetcher:
    def __init__(self, categories: list[str], request_interval_seconds: int = 3):
        self._categories = categories
        self._interval = request_interval_seconds

    async def fetch(
        self,
        date_from: date,
        date_to: date,
        max_results: int = 500,
    ) -> list[RawPaper]:
        cat_query = " OR ".join(f"cat:{c}" for c in self._categories)
        date_range = (
            f"submittedDate:[{date_from.strftime('%Y%m%d')}0000 TO {date_to.strftime('%Y%m%d')}2359]"
        )
        search_query = f"({cat_query}) AND {date_range}"

        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(ARXIV_API_URL, params=params)
                    if response.status_code == 503:
                        raise httpx.HTTPStatusError(
                            "503", request=response.request, response=response
                        )
                    response.raise_for_status()
                    return self.parse_atom_response(response.text)
            except Exception:
                wait = 3 ** (attempt + 1)
                logger.warning(
                    "arXiv request failed (attempt %d/3), retrying in %ds", attempt + 1, wait
                )
                if attempt < 2:
                    await asyncio.sleep(wait)
        return []

    def parse_atom_response(self, xml_text: str) -> list[RawPaper]:
        root = ET.fromstring(xml_text)
        papers: list[RawPaper] = []

        for entry in root.findall(f"{{{ATOM_NS}}}entry"):
            id_elem = entry.find(f"{{{ATOM_NS}}}id")
            if id_elem is None or id_elem.text is None:
                continue

            arxiv_id = self._extract_arxiv_id(id_elem.text)
            title_elem = entry.find(f"{{{ATOM_NS}}}title")
            summary_elem = entry.find(f"{{{ATOM_NS}}}summary")
            published_elem = entry.find(f"{{{ATOM_NS}}}published")

            title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
            abstract = (
                summary_elem.text.strip() if summary_elem is not None and summary_elem.text else ""
            )

            authors = []
            for author_elem in entry.findall(f"{{{ATOM_NS}}}author"):
                name_elem = author_elem.find(f"{{{ATOM_NS}}}name")
                if name_elem is not None and name_elem.text:
                    authors.append(name_elem.text)

            categories = []
            for cat_elem in entry.findall(f"{{{ATOM_NS}}}category"):
                term = cat_elem.get("term")
                if term:
                    categories.append(term)

            published_date_val = None
            if published_elem is not None and published_elem.text:
                published_date_val = date.fromisoformat(published_elem.text[:10])

            pdf_url = None
            source_url = None
            for link in entry.findall(f"{{{ATOM_NS}}}link"):
                if link.get("title") == "pdf":
                    pdf_url = link.get("href")
                elif link.get("rel") == "alternate":
                    source_url = link.get("href")

            papers.append(
                RawPaper(
                    source="arxiv",
                    source_record_id=arxiv_id or "",
                    arxiv_id=arxiv_id,
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    arxiv_categories=categories,
                    published_date=published_date_val,
                    pdf_url=pdf_url,
                    source_url=source_url,
                )
            )

        return papers

    @staticmethod
    def _extract_arxiv_id(url: str) -> str | None:
        match = _ARXIV_ID_RE.search(url)
        return match.group(1) if match else None
