"""Batch download PDFs for all papers that don't have paper_files yet."""
from __future__ import annotations

import asyncio
import logging
import sys

from backend.core.database import Database
from backend.core.stage_runner import StageRunner
from backend.pdf.fetcher import PdfFetcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
)
logger = logging.getLogger(__name__)

DB_PATH = "data/tracker.db"
PAPER_ROOT = "data/papers"
MAX_CONCURRENT = 5
DOWNLOAD_TIMEOUT = 120


async def main():
    db = Database(DB_PATH)
    await db.initialize()
    stage_runner = StageRunner(db)
    fetcher = PdfFetcher(
        db=db,
        stage_runner=stage_runner,
        paper_root=PAPER_ROOT,
        download_timeout=DOWNLOAD_TIMEOUT,
    )

    # Find papers without paper_files
    papers = await db.fetch_all(
        "SELECT p.id FROM papers p "
        "LEFT JOIN paper_files pf ON p.id = pf.paper_id "
        "WHERE pf.id IS NULL"
    )
    logger.info("Found %d papers without PDFs", len(papers))

    if not papers:
        logger.info("Nothing to do")
        await db.close()
        return

    # Create pdf_fetch stage_runs for papers that don't have one
    created = 0
    for p in papers:
        paper_id = p["id"]
        pdf_url = f"https://arxiv.org/pdf/{paper_id}"
        run_id = await stage_runner.create(
            target_type="paper",
            target_id=paper_id,
            stage="pdf_fetch",
            payload={"pdf_url": pdf_url},
        )
        created += 1
    logger.info("Created %d pdf_fetch stage_runs", created)

    # Process downloads with concurrency control
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    succeeded = 0
    failed = 0

    async def download_one():
        nonlocal succeeded, failed
        async with sem:
            try:
                result = await fetcher.process_next()
                if result:
                    succeeded += 1
                return result
            except Exception as e:
                failed += 1
                logger.error("Download error: %s", e)
                return True

    # Keep processing until no more pending tasks
    batch_num = 0
    while True:
        pending = await stage_runner.list_by_status("pdf_fetch", "pending")
        if not pending:
            break
        batch_num += 1
        logger.info("Batch %d: %d pending downloads", batch_num, len(pending))

        tasks = [asyncio.create_task(download_one()) for _ in pending]
        await asyncio.gather(*tasks)
        logger.info("Progress: %d succeeded, %d failed", succeeded, failed)

    logger.info("Done! Total: %d succeeded, %d failed out of %d papers",
                succeeded, failed, len(papers))

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
