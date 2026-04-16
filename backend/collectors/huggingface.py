from __future__ import annotations

import asyncio
import logging
from datetime import date

import httpx

from backend.collectors.raw_paper import RawPaper

logger = logging.getLogger(__name__)

HF_DAILY_PAPERS_URL = "https://huggingface.co/api/daily_papers"


class HuggingFaceFetcher:
    def __init__(self, request_interval_seconds: int = 3):
        self._interval = request_interval_seconds

    async def fetch(self, target_date: date) -> list[RawPaper]:
        url = f"{HF_DAILY_PAPERS_URL}?date={target_date.isoformat()}"

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url)
                    if response.status_code >= 500:
                        raise httpx.HTTPStatusError(
                            f"{response.status_code}", request=response.request, response=response
                        )
                    response.raise_for_status()
                    return self.parse_response(response.json())
            except Exception:
                wait = 3 ** (attempt + 1)
                logger.warning(
                    "HuggingFace request failed (attempt %d/3), retrying in %ds",
                    attempt + 1,
                    wait,
                )
                if attempt < 2:
                    await asyncio.sleep(wait)
        return []

    def parse_response(self, data: list[dict]) -> list[RawPaper]:
        papers: list[RawPaper] = []

        for item in data:
            paper_data = item.get("paper", {})
            paper_id = paper_data.get("id", "")

            authors = []
            for author in paper_data.get("authors", []):
                name = author.get("name")
                if name:
                    authors.append(name)

            published_date_val = None
            published_str = paper_data.get("publishedAt")
            if published_str:
                try:
                    published_date_val = date.fromisoformat(published_str[:10])
                except ValueError:
                    pass

            papers.append(
                RawPaper(
                    source="huggingface",
                    source_record_id=paper_id,
                    arxiv_id=paper_id if paper_id else None,
                    title=paper_data.get("title", ""),
                    authors=authors,
                    abstract=paper_data.get("summary", ""),
                    published_date=published_date_val,
                    source_url=f"https://huggingface.co/papers/{paper_id}" if paper_id else None,
                    hf_likes=paper_data.get("upvotes"),
                    hf_discussions=item.get("numComments"),
                )
            )

        return papers
