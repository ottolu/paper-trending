"""Run the full downstream pipeline (processor -> analyzer) over ALL pending papers,
with the analyzer LLM calls running concurrently via a fixed worker pool.

Safe to run concurrently now that StageRunner.claim() is atomic (single-statement
UPDATE ... RETURNING). Each worker loops process_next(); the atomic claim hands
each a distinct task.

Usage:
    .venv/bin/python -m scripts.analyze_all --analyzer-concurrency 8 --retry-rounds 2
"""
from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import time
from pathlib import Path

from dotenv import load_dotenv

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
load_dotenv()

from backend.analyzer.service import AnalyzerService
from backend.core.database import Database
from backend.core.embedding_client import EmbeddingClient
from backend.core.llm_client import LLMClient
from backend.core.stage_runner import StageRunner
from backend.core.vector_store import VectorStore
from backend.processor.service import ProcessorService

DATA_ROOT = Path("data")
DS_BASE_URL = "https://api.deepseek.com"
SF_BASE_URL = "https://api.siliconflow.cn/v1"
LLM_MODEL = "deepseek-v4-pro"
EMBED_MODEL = "Qwen/Qwen3-Embedding-8B"


async def run_pool(service, n_workers: int, prefix: str, label: str, total: int) -> int:
    """N workers each loop process_next() until the queue drains."""
    done = {"n": 0}

    async def worker(wid: int) -> None:
        while await service.process_next(f"{prefix}-{wid}"):
            done["n"] += 1
            if done["n"] % 10 == 0 or done["n"] == total:
                print(f"  {label}: {done['n']}/{total}", flush=True)

    await asyncio.gather(*[worker(i) for i in range(n_workers)])
    return done["n"]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--analyzer-concurrency", type=int, default=8)
    ap.add_argument("--processor-concurrency", type=int, default=8)
    ap.add_argument("--retry-rounds", type=int, default=2)
    args = ap.parse_args()

    db = Database(str(DATA_ROOT / "tracker.db"))
    await db.initialize()
    sr = StageRunner(db)
    paper_root = str(DATA_ROOT / "papers")

    llm = LLMClient(
        base_url=DS_BASE_URL, api_key=os.environ["DEEPSEEK_API_KEY"],
        model=LLM_MODEL, enable_thinking=True,
    )
    embedding = EmbeddingClient(
        base_url=SF_BASE_URL, api_key=os.environ["SILICONFLOW_API_KEY"], model=EMBED_MODEL
    )
    vs = VectorStore(persist_dir=str(DATA_ROOT / "chromadb"))
    processor = ProcessorService(db=db, stage_runner=sr, paper_root=paper_root)
    analyzer = AnalyzerService(
        db=db, stage_runner=sr, paper_root=paper_root,
        llm_client=llm, embedding_client=embedding, vector_store=vs,
    )

    # capture LLM token usage for real cost
    usage = {"pt": 0, "ct": 0, "calls": 0}
    orig_create = llm._client.chat.completions.create

    async def wrapped_create(*a, **k):
        resp = await orig_create(*a, **k)
        u = getattr(resp, "usage", None)
        if u:
            usage["pt"] += getattr(u, "prompt_tokens", 0) or 0
            usage["ct"] += getattr(u, "completion_tokens", 0) or 0
            usage["calls"] += 1
        return resp

    llm._client.chat.completions.create = wrapped_create

    try:
        # ---- processor ----
        n_proc = len(await sr.list_by_status("processor", "pending", limit=10000))
        print(f"processor: {n_proc} pending", flush=True)
        t0 = time.time()
        await run_pool(processor, args.processor_concurrency, "proc", "processor", n_proc)
        print(f"processor done in {time.time() - t0:.0f}s", flush=True)

        # ---- analyzer (concurrent) ----
        n_an = len(await sr.list_by_status("analyzer", "pending", limit=10000))
        print(f"analyzer: {n_an} pending, concurrency={args.analyzer_concurrency}", flush=True)
        t1 = time.time()
        await run_pool(analyzer, args.analyzer_concurrency, "an", "analyzer", n_an)
        an_time = time.time() - t1

        # ---- retry failures ----
        for rnd in range(args.retry_rounds):
            failed = await sr.list_by_status("analyzer", "failed", limit=10000)
            if not failed:
                break
            print(f"retry round {rnd + 1}: {len(failed)} failed -> requeue", flush=True)
            for f in failed:
                await sr.retry(f["id"])
            await run_pool(analyzer, args.analyzer_concurrency, f"an-r{rnd}", "retry", len(failed))

        # ---- report ----
        succeeded = await db.fetch_all(
            "SELECT paper_id, score_total FROM analysis_runs WHERE status='succeeded'"
        )
        by_paper = {}
        for r in succeeded:
            by_paper.setdefault(r["paper_id"], []).append(r["score_total"])
        scores = [v[-1] for v in by_paper.values()]
        dupes = {p: len(v) for p, v in by_paper.items() if len(v) > 1}
        failed = await db.fetch_all(
            "SELECT target_id, last_error FROM stage_runs WHERE stage='analyzer' AND status='failed'"
        )
        bases = await db.fetch_all(
            "SELECT analysis_basis, COUNT(*) c FROM analysis_runs GROUP BY analysis_basis"
        )
        cost = (usage["pt"] * 0.28 + usage["ct"] * 0.42) / 1e6

        print("=" * 64)
        print(f"analyzer wall: {an_time:.0f}s for {n_an} papers "
              f"({an_time / max(n_an,1):.0f}s/paper effective @ {args.analyzer_concurrency}x)")
        print(f"distinct papers analyzed: {len(by_paper)} | "
              f"total analysis_runs(succeeded): {len(succeeded)}")
        if scores:
            print(f"score_total: min {min(scores)} median {statistics.median(scores)} "
                  f"max {max(scores)} mean {statistics.mean(scores):.2f}")
        print(f"analysis_basis: {[(b['analysis_basis'], b['c']) for b in bases]}")
        print(f"tokens: in {usage['pt']} out {usage['ct']} ({usage['calls']} calls) "
              f"-> cost ${cost:.2f} (ASSUMED $0.28/$0.42 per-M)")
        if dupes:
            print(f"WARNING duplicate analysis_runs for {len(dupes)} papers: {dupes}")
        print(f"failed analyzer: {len(failed)}")
        for f in failed[:15]:
            print("  FAIL", f["target_id"], "->", (f["last_error"] or "")[:100])
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
