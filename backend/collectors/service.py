from __future__ import annotations

import json
import logging
from datetime import date

from backend.collectors.arxiv import ArxivFetcher
from backend.collectors.huggingface import HuggingFaceFetcher
from backend.collectors.linker import LinkedPaper, PaperLinker
from backend.collectors.raw_paper import RawPaper
from backend.core.database import Database
from backend.core.stage_runner import StageRunner

logger = logging.getLogger(__name__)


class CollectorService:
    def __init__(
        self,
        db: Database,
        stage_runner: StageRunner,
        arxiv_categories: list[str] | None = None,
        arxiv_interval: int = 3,
        hf_interval: int = 3,
        fuzzy_threshold: float = 0.85,
    ):
        self._db = db
        self._stage_runner = stage_runner
        self._arxiv_fetcher = ArxivFetcher(
            categories=arxiv_categories or ["cs.CL", "cs.AI", "cs.LG"],
            request_interval_seconds=arxiv_interval,
        )
        self._hf_fetcher = HuggingFaceFetcher(request_interval_seconds=hf_interval)
        self._linker = PaperLinker(fuzzy_threshold=fuzzy_threshold)

    async def collect(
        self,
        date_from: date,
        date_to: date,
    ) -> dict:
        arxiv_papers = await self._fetch_arxiv(date_from, date_to)
        hf_papers = await self._fetch_hf(date_to)
        linked = self._linker.link(arxiv_papers, hf_papers)

        papers_upserted = 0
        sources_created = 0

        for lp in linked:
            result = await self.upsert_paper(lp)
            papers_upserted += 1
            sources_created += result["sources_created"]

        logger.info(
            "Collection complete: %d papers upserted, %d sources created",
            papers_upserted,
            sources_created,
        )

        return {
            "papers_upserted": papers_upserted,
            "sources_created": sources_created,
        }

    async def upsert_paper(self, lp: LinkedPaper) -> dict:
        existing = await self._db.fetch_one(
            "SELECT id FROM papers WHERE id = ?", (lp.paper_id,)
        )

        if existing:
            await self._db.execute(
                "UPDATE papers SET title = ?, authors = ?, abstract = ?, "
                "arxiv_categories = ?, published_date = ?, updated_at = datetime('now') "
                "WHERE id = ?",
                (
                    lp.title,
                    json.dumps(lp.authors),
                    lp.abstract,
                    json.dumps(lp.arxiv_categories),
                    lp.published_date.isoformat() if lp.published_date else None,
                    lp.paper_id,
                ),
            )
        else:
            await self._db.execute(
                "INSERT INTO papers (id, arxiv_id, title, authors, abstract, arxiv_categories, "
                "published_date, first_seen_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))",
                (
                    lp.paper_id,
                    lp.arxiv_id,
                    lp.title,
                    json.dumps(lp.authors),
                    lp.abstract,
                    json.dumps(lp.arxiv_categories),
                    lp.published_date.isoformat() if lp.published_date else None,
                ),
            )

        sources_created = 0

        if lp.arxiv_source:
            sources_created += await self._upsert_source(lp.paper_id, lp.arxiv_source, lp)

        if lp.hf_source:
            sources_created += await self._upsert_source(lp.paper_id, lp.hf_source, lp)

        if lp.pdf_url:
            await self._stage_runner.create(
                target_type="paper",
                target_id=lp.paper_id,
                stage="pdf_fetch",
                payload={"pdf_url": lp.pdf_url},
            )

        return {"sources_created": sources_created}

    async def _upsert_source(
        self,
        paper_id: str,
        raw: RawPaper,
        lp: LinkedPaper,
    ) -> int:
        existing = await self._db.fetch_one(
            "SELECT id FROM paper_sources WHERE paper_id = ? AND source_name = ?",
            (paper_id, raw.source),
        )
        if existing:
            return 0

        await self._db.execute(
            "INSERT INTO paper_sources (paper_id, source_name, source_url, source_record_id, "
            "match_strategy, match_confidence, hf_likes, hf_discussions, collected_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
            (
                paper_id,
                raw.source,
                raw.source_url,
                raw.source_record_id,
                lp.match_strategy if raw.source != "arxiv" else "arxiv_id",
                lp.match_confidence if raw.source != "arxiv" else 1.0,
                raw.hf_likes,
                raw.hf_discussions,
            ),
        )
        return 1

    async def _fetch_arxiv(self, date_from: date, date_to: date) -> list[RawPaper]:
        return await self._arxiv_fetcher.fetch(date_from=date_from, date_to=date_to)

    async def _fetch_hf(self, target_date: date) -> list[RawPaper]:
        return await self._hf_fetcher.fetch(target_date=target_date)
