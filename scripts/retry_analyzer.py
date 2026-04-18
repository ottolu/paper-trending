"""Retry failed analyzer tasks one at a time with rate limit backoff."""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging

from backend.core.database import Database
from backend.core.embedding_client import EmbeddingClient
from backend.core.llm_client import LLMClient
from backend.core.stage_runner import StageRunner
from backend.core.vector_store import VectorStore
from backend.analyzer.service import AnalyzerService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("retry")

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"
SF_BASE_URL = "https://api.siliconflow.cn/v1"
SF_API_KEY = "sk-sazyhdorjrvicvtglqqfwrnogqkoyghudvcxmhnzvdwbxjlp"
LLM_MODEL = "Qwen/Qwen3-VL-235B-A22B-Thinking"
EMBED_MODEL = "Qwen/Qwen3-Embedding-8B"


async def main():
    db = Database(str(DATA_ROOT / "tracker.db"))
    await db.initialize()
    sr = StageRunner(db)

    # Reset failed analyzer tasks to pending
    failed = await db.fetch_all(
        "SELECT id FROM stage_runs WHERE stage = 'analyzer' AND status = 'failed'"
    )
    for f in failed:
        await sr.retry(f["id"])
    logger.info("Reset %d failed analyzer tasks to pending", len(failed))

    llm = LLMClient(base_url=SF_BASE_URL, api_key=SF_API_KEY, model=LLM_MODEL)
    embedding = EmbeddingClient(base_url=SF_BASE_URL, api_key=SF_API_KEY, model=EMBED_MODEL)
    vs = VectorStore(persist_dir=str(DATA_ROOT / "chromadb"))

    analyzer = AnalyzerService(
        db=db,
        stage_runner=sr,
        paper_root=str(DATA_ROOT / "papers"),
        llm_client=llm,
        embedding_client=embedding,
        vector_store=vs,
    )

    succeeded = 0
    failed_count = 0
    start = time.time()
    delay = 5  # seconds between requests

    while True:
        result = await analyzer.process_next()
        if not result:
            break

        # Check if it succeeded or failed
        ok = await db.fetch_one(
            "SELECT count(*) as c FROM analysis_runs WHERE status = 'succeeded'"
        )
        current_ok = ok["c"]

        if current_ok > succeeded:
            succeeded = current_ok
            delay = max(3, delay - 1)  # speed up on success
            logger.info(
                "Succeeded: %d | Failed: %d | Delay: %ds | Elapsed: %.0fs",
                succeeded, failed_count, delay, time.time() - start,
            )
        else:
            failed_count += 1
            delay = min(30, delay + 5)  # back off on failure
            logger.warning("Rate limited, backing off to %ds", delay)

        await asyncio.sleep(delay)

    # Summary
    total_ok = await db.fetch_one(
        "SELECT count(*) as c FROM analysis_runs WHERE status = 'succeeded' "
        "AND analysis_basis = 'full_text'"
    )
    total_fail = await db.fetch_one(
        "SELECT count(*) as c FROM stage_runs WHERE stage = 'analyzer' AND status = 'failed'"
    )
    logger.info("=" * 60)
    logger.info(
        "DONE: %d full-text analyses succeeded, %d failed, %.0fs elapsed",
        total_ok["c"], total_fail["c"], time.time() - start,
    )
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
