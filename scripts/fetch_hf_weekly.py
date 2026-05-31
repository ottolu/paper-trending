"""Fetch HuggingFace Daily Papers grouped by ISO week, take the top-N per week
(by HF upvotes), and ingest them into the pipeline DB.

For each selected paper we:
  1. upsert into `papers` (keyed by arXiv id) + `paper_sources` (huggingface, hf_likes)
  2. queue a `pdf_fetch` stage_run pointing at https://arxiv.org/pdf/<id>
  3. drive PdfFetcher so the PDF lands at
     data/papers/<arxiv_id>/files/versions/<sha256>.pdf

The week is only a transient sourcing filter -- it is NOT persisted as a folder
or column. The only weekly signal kept is hf_likes (a per-week upvote snapshot)
on paper_sources. Papers appearing in two weeks' top-N collapse to one row,
since the arXiv id is the primary key.

Usage:
    .venv/bin/python -m scripts.fetch_hf_weekly            # last 4 complete weeks, top 30
    .venv/bin/python -m scripts.fetch_hf_weekly --weeks 4 --top 30 --concurrency 5
"""
from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import logging
import os
import urllib.request

from backend.collectors.huggingface import HuggingFaceFetcher
from backend.collectors.linker import LinkedPaper
from backend.collectors.service import CollectorService
from backend.core.database import Database
from backend.core.stage_runner import StageRunner
from backend.pdf.fetcher import PdfFetcher

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
logger = logging.getLogger("fetch_hf_weekly")

HF_WEEKLY_URL = "https://huggingface.co/api/daily_papers?week={week}"
ARXIV_PDF_URL = "https://arxiv.org/pdf/{arxiv_id}"  # no extension -> 200 application/pdf


def last_complete_iso_weeks(today: datetime.date, n: int) -> list[str]:
    """Return the `n` most recent *complete* ISO weeks (newest first).

    If today is mid-week, the current (partial) week is skipped so each week
    has a full set of daily papers to rank.
    """
    # isoweekday(): Mon=1..Sun=7. Step back to the last Sunday (end of an ISO week).
    anchor = today - datetime.timedelta(days=today.isoweekday() % 7)
    weeks: list[str] = []
    d = anchor
    while len(weeks) < n:
        iso = d.isocalendar()
        tag = f"{iso[0]}-W{iso[1]:02d}"
        if tag not in weeks:
            weeks.append(tag)
        d -= datetime.timedelta(days=7)
    return weeks


def fetch_week(week: str) -> list[dict]:
    req = urllib.request.Request(
        HF_WEEKLY_URL.format(week=week), headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weeks", type=int, default=4, help="number of recent complete ISO weeks")
    parser.add_argument("--top", type=int, default=30, help="top-N papers per week (by upvotes)")
    parser.add_argument("--today", type=str, default=None, help="override 'today' as YYYY-MM-DD")
    parser.add_argument("--data-root", type=str, default="data")
    args = parser.parse_args()

    today = datetime.date.fromisoformat(args.today) if args.today else datetime.date.today()
    weeks = last_complete_iso_weeks(today, args.weeks)
    logger.info("Today=%s -> target weeks (newest first): %s | top %d each", today, weeks, args.top)

    os.makedirs(args.data_root, exist_ok=True)
    db = Database(f"{args.data_root}/tracker.db")
    await db.initialize()
    stage_runner = StageRunner(db)
    service = CollectorService(db, stage_runner)
    hf = HuggingFaceFetcher()

    # ---- Sourcing + ingest -------------------------------------------------
    seen: set[str] = set()
    selections = 0
    week_summary: dict[str, dict] = {}
    for week in weeks:
        raw = hf.parse_response(fetch_week(week))  # already upvote-desc
        top = raw[: args.top]
        top_paper = top[0] if top else None
        week_summary[week] = {
            "selected": len(top),
            "top": (top_paper.arxiv_id, top_paper.hf_likes, top_paper.title) if top_paper else None,
        }
        for rp in top:
            arxiv_id = rp.arxiv_id or rp.source_record_id
            if not arxiv_id:
                logger.warning("Skip paper without id: %s", rp.title)
                continue
            if arxiv_id in seen:
                continue
            seen.add(arxiv_id)
            lp = LinkedPaper(
                paper_id=arxiv_id,
                title=rp.title,
                authors=rp.authors,
                abstract=rp.abstract or "",
                arxiv_id=arxiv_id,
                arxiv_categories=[],
                published_date=rp.published_date,
                pdf_url=ARXIV_PDF_URL.format(arxiv_id=arxiv_id),
                arxiv_source=None,
                hf_source=rp,
                match_strategy="hf_weekly",
                match_confidence=None,
            )
            await service.upsert_paper(lp)
            selections += 1

    logger.info(
        "Ingested: %d selections across %d weeks -> %d unique papers (pdf_fetch queued)",
        selections, len(weeks), len(seen),
    )

    # ---- Drive pdf_fetch to completion --------------------------------------
    # Sequential on purpose: StageRunner.claim() has a SELECT-then-UPDATE race
    # under concurrency (duplicate stage_run_attempts), and 120 PDFs over the
    # arXiv CDN finish in a few minutes single-threaded anyway.
    total_pending = len(await stage_runner.list_by_status("pdf_fetch", "pending", limit=10000))
    logger.info("Downloading %d PDFs sequentially ...", total_pending)
    fetcher = PdfFetcher(db, stage_runner, paper_root=f"{args.data_root}/papers")
    processed = 0
    while await fetcher.process_next("weekly-fetcher"):
        processed += 1
        if processed % 10 == 0 or processed == total_pending:
            logger.info("  ... %d/%d processed", processed, total_pending)

    # ---- Report ------------------------------------------------------------
    totals = await db.fetch_one(
        "SELECT COUNT(*) c, COALESCE(SUM(file_size_bytes),0) b FROM paper_files"
    )
    failed = await db.fetch_all(
        "SELECT target_id, last_error FROM stage_runs "
        "WHERE stage='pdf_fetch' AND status='failed' ORDER BY target_id"
    )
    logger.info("=" * 60)
    for week in weeks:
        s = week_summary[week]
        t = s["top"]
        top_str = f"#1 {t[0]} ({t[1]}↑) {t[2][:50]}" if t else "(empty)"
        logger.info("  %s: %d selected | %s", week, s["selected"], top_str)
    logger.info("=" * 60)
    logger.info(
        "DONE: %d unique papers ingested, %d PDFs on disk (%.1f MB), %d failed",
        len(seen), totals["c"], totals["b"] / 1e6, len(failed),
    )
    if failed:
        logger.warning("Failed downloads:")
        for f in failed:
            logger.warning("  %s -> %s", f["target_id"], f["last_error"])

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
