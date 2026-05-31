"""Retry failed analyzer tasks until reaching target count."""
import asyncio
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
load_dotenv()
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
TARGET = 20


async def main():
    db = Database(str(DATA_ROOT / "tracker.db"))
    await db.initialize()
    sr = StageRunner(db)

    # Reset failed analyzer tasks
    failed = await db.fetch_all(
        "SELECT id FROM stage_runs WHERE stage = 'analyzer' AND status = 'failed'"
    )
    for f in failed:
        await sr.retry(f["id"])
    logger.info("Reset %d failed tasks", len(failed))

    llm = LLMClient(
        base_url="https://api.deepseek.com",
        api_key=os.environ["DEEPSEEK_API_KEY"],
        model="deepseek-v4-pro",
        enable_thinking=True,
    )
    embedding = EmbeddingClient(
        base_url="https://api.siliconflow.cn/v1",
        api_key=os.environ["SILICONFLOW_API_KEY"],
        model="Qwen/Qwen3-Embedding-8B",
    )
    vs = VectorStore(persist_dir=str(DATA_ROOT / "chromadb"))

    analyzer = AnalyzerService(
        db=db, stage_runner=sr, paper_root=str(DATA_ROOT / "papers"),
        llm_client=llm, embedding_client=embedding, vector_store=vs,
    )

    start = time.time()
    delay = 8

    while True:
        # Check current count
        ok = await db.fetch_one(
            "SELECT count(*) as c FROM analysis_runs WHERE status='succeeded' AND analysis_basis='full_text'"
        )
        if ok["c"] >= TARGET:
            logger.info("Reached target: %d full-text analyses", ok["c"])
            break

        result = await analyzer.process_next()
        if not result:
            logger.info("No more pending tasks")
            break

        # Check if it succeeded
        new_ok = await db.fetch_one(
            "SELECT count(*) as c FROM analysis_runs WHERE status='succeeded' AND analysis_basis='full_text'"
        )
        if new_ok["c"] > ok["c"]:
            delay = max(5, delay - 1)
            logger.info("OK %d/%d | delay=%ds | %.0fs", new_ok["c"], TARGET, delay, time.time() - start)
        else:
            delay = min(45, delay + 10)
            logger.warning("Failed (429?), backoff to %ds", delay)

        await asyncio.sleep(delay)

    total = await db.fetch_one(
        "SELECT count(*) as c FROM analysis_runs WHERE status='succeeded' AND analysis_basis='full_text'"
    )
    logger.info("DONE: %d full-text analyses", total["c"])
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
