"""Run full pipeline on test set: pdf_fetch → pdf_parse → processor → analyzer.

Usage:
    python scripts/run_full_pipeline.py [--max-papers N] [--skip-fetch] [--skip-parse]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.core.database import Database
from backend.core.embedding_client import EmbeddingClient
from backend.core.llm_client import LLMClient
from backend.core.stage_runner import StageRunner
from backend.core.vector_store import VectorStore
from backend.pdf.fetcher import PdfFetcher
from backend.pdf.parser import PdfParser
from backend.processor.service import ProcessorService
from backend.analyzer.service import AnalyzerService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("pipeline")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = PROJECT_ROOT / "data"

SF_BASE_URL = "https://api.siliconflow.cn/v1"
SF_API_KEY = "sk-sazyhdorjrvicvtglqqfwrnogqkoyghudvcxmhnzvdwbxjlp"
LLM_MODEL = "Qwen/Qwen3-VL-235B-A22B-Thinking"
EMBED_MODEL = "Qwen/Qwen3-Embedding-8B"


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-papers", type=int, default=40)
    parser.add_argument("--skip-fetch", action="store_true")
    parser.add_argument("--skip-parse", action="store_true")
    args = parser.parse_args()

    db = Database(str(DATA_ROOT / "tracker.db"))
    await db.initialize()
    sr = StageRunner(db)
    paper_root = str(DATA_ROOT / "papers")

    # Load test set + held-out paper IDs
    test_data = json.loads((DATA_ROOT / "eval_test_set.json").read_text())
    paper_ids = [p["id"] for p in test_data["test_set"]] + [
        p["id"] for p in test_data["held_out"]
    ]
    paper_ids = paper_ids[: args.max_papers]
    logger.info("Pipeline for %d papers", len(paper_ids))

    # --- Step 1: PDF Fetch ---
    if not args.skip_fetch:
        for pid in paper_ids:
            # Check if already downloaded
            existing = await db.fetch_one(
                "SELECT id FROM paper_files WHERE paper_id = ? AND is_current = 1", (pid,)
            )
            if not existing:
                pdf_url = f"https://arxiv.org/pdf/{pid}"
                await sr.create(
                    target_type="paper",
                    target_id=pid,
                    stage="pdf_fetch",
                    payload={"pdf_url": pdf_url},
                )

        fetcher = PdfFetcher(db=db, stage_runner=sr, paper_root=paper_root)
        fetched = 0
        start = time.time()
        while True:
            result = await fetcher.process_next()
            if not result:
                break
            fetched += 1
            if fetched % 5 == 0:
                logger.info("Fetched %d PDFs (%.0fs)", fetched, time.time() - start)
        logger.info("PDF fetch complete: %d new files (%.0fs)", fetched, time.time() - start)
    else:
        logger.info("Skipping PDF fetch")

    # --- Step 2: PDF Parse (marker-pdf, no OCR) ---
    if not args.skip_parse:
        for pid in paper_ids:
            # Check if already parsed
            existing = await db.fetch_one(
                "SELECT id FROM pdf_extractions WHERE paper_id = ? "
                "AND extraction_status = 'succeeded'",
                (pid,),
            )
            if not existing:
                pf = await db.fetch_one(
                    "SELECT id FROM paper_files WHERE paper_id = ? AND is_current = 1",
                    (pid,),
                )
                if pf:
                    await sr.create(
                        target_type="paper",
                        target_id=pid,
                        stage="pdf_parse",
                        payload={"paper_file_id": pf["id"]},
                    )

        pdf_parser = PdfParser(
            db=db,
            stage_runner=sr,
            paper_root=paper_root,
            parser_name="marker",
            parser_version="v1",
        )
        parsed = 0
        start = time.time()
        while True:
            result = await pdf_parser.process_next()
            if not result:
                break
            parsed += 1
            logger.info("Parsed %d (%.0fs elapsed)", parsed, time.time() - start)
        logger.info("PDF parse complete: %d files (%.0fs)", parsed, time.time() - start)
    else:
        logger.info("Skipping PDF parse")

    # --- Step 3: Processor (chunking) ---
    for pid in paper_ids:
        ext = await db.fetch_one(
            "SELECT id FROM pdf_extractions WHERE paper_id = ? "
            "AND extraction_status = 'succeeded'",
            (pid,),
        )
        if ext:
            await sr.create(target_type="paper", target_id=pid, stage="processor")

    processor = ProcessorService(db=db, stage_runner=sr, paper_root=paper_root)
    processed = 0
    while True:
        result = await processor.process_next()
        if not result:
            break
        processed += 1
    logger.info("Processor complete: %d papers", processed)

    # --- Step 4: Analyzer ---
    llm = LLMClient(base_url=SF_BASE_URL, api_key=SF_API_KEY, model=LLM_MODEL)
    embedding = EmbeddingClient(base_url=SF_BASE_URL, api_key=SF_API_KEY, model=EMBED_MODEL)
    vs = VectorStore(persist_dir=str(DATA_ROOT / "chromadb"))

    analyzer_svc = AnalyzerService(
        db=db,
        stage_runner=sr,
        paper_root=paper_root,
        llm_client=llm,
        embedding_client=embedding,
        vector_store=vs,
    )

    analyzed = 0
    start = time.time()
    while True:
        result = await analyzer_svc.process_next()
        if not result:
            break
        analyzed += 1
        if analyzed % 5 == 0:
            logger.info("Analyzed %d (%.0fs)", analyzed, time.time() - start)
    logger.info("Analyzer complete: %d papers (%.0fs)", analyzed, time.time() - start)

    # --- Summary ---
    full_text = await db.fetch_one(
        "SELECT count(*) as c FROM analysis_runs WHERE status='succeeded' "
        "AND analysis_basis='full_text'"
    )
    abstract_only = await db.fetch_one(
        "SELECT count(*) as c FROM analysis_runs WHERE status='succeeded' "
        "AND analysis_basis='abstract_only'"
    )
    fail = await db.fetch_one(
        "SELECT count(*) as c FROM stage_runs WHERE stage='analyzer' AND status='failed'"
    )
    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info(
        "Full-text: %d | Abstract-only: %d | Failed: %d",
        full_text["c"],
        abstract_only["c"],
        fail["c"],
    )

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
