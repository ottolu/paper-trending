"""Benchmark the downstream pipeline (processor + analyzer) on a small, size-spread
sample of already-parsed papers, to get REAL per-paper LLM latency + token cost
under the new deepseek-v4-pro (thinking) wiring before scaling to 6-12 months.

Safety: parse auto-creates a `processor` stage_run for every paper. To avoid
running the whole corpus, we HOLD all non-sampled processor tasks (status flipped
away from 'pending' so claim() skips them) and RESTORE them in a finally block.

Token usage is captured by wrapping the OpenAI client's create() (LLMClient.chat
discards response.usage).

Usage:
    .venv/bin/python -m scripts.bench_downstream --n 8 --in-price 0.28 --out-price 0.42
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


async def select_spread(db: Database, n: int) -> list[tuple[str, int]]:
    rows = await db.fetch_all(
        "SELECT paper_id, page_count FROM pdf_extractions "
        "WHERE extraction_status='succeeded' ORDER BY page_count"
    )
    if len(rows) <= n:
        return [(r["paper_id"], r["page_count"]) for r in rows]
    idx = [round(i * (len(rows) - 1) / (n - 1)) for i in range(n)]
    return [(rows[i]["paper_id"], rows[i]["page_count"]) for i in idx]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--in-price", type=float, default=0.28, help="$/M prompt tokens (ASSUMED)")
    ap.add_argument("--out-price", type=float, default=0.42, help="$/M completion tokens (ASSUMED)")
    args = ap.parse_args()

    db = Database(str(DATA_ROOT / "tracker.db"))
    await db.initialize()
    sr = StageRunner(db)
    paper_root = str(DATA_ROOT / "papers")

    sample = await select_spread(db, args.n)
    ids = [pid for pid, _ in sample]
    pages = {pid: pg for pid, pg in sample}
    print(f"sample ({len(ids)}): {sample}")

    # HOLD all non-sampled pending processor tasks so we only process the sample.
    placeholders = ",".join("?" for _ in ids)
    held = await db.execute(
        f"UPDATE stage_runs SET status='held_bench' "
        f"WHERE stage='processor' AND status='pending' AND target_id NOT IN ({placeholders})",
        tuple(ids),
    )
    print(f"held {held} non-sample processor tasks (will restore in finally)")

    try:
        # ---- wiring (mirrors run_full_pipeline.py) ----
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

        # ---- capture LLM token usage by wrapping create() ----
        usage_log: list[dict] = []
        orig_create = llm._client.chat.completions.create

        async def wrapped_create(*a, **k):
            t = time.time()
            resp = await orig_create(*a, **k)
            u = getattr(resp, "usage", None)
            usage_log.append({
                "pt": getattr(u, "prompt_tokens", 0) or 0,
                "ct": getattr(u, "completion_tokens", 0) or 0,
                "tt": getattr(u, "total_tokens", 0) or 0,
                "wall": time.time() - t,
            })
            return resp

        llm._client.chat.completions.create = wrapped_create

        # ---- Step 1: processor (chunk + embed) on the sample ----
        t0 = time.time()
        proc = 0
        while await processor.process_next("bench-proc"):
            proc += 1
        proc_time = time.time() - t0
        print(f"processor: {proc} papers in {proc_time:.1f}s ({proc_time / max(proc,1):.1f}s/paper)")

        # ---- Step 2: analyzer (LLM) on the sample ----
        pending_an = await sr.list_by_status("analyzer", "pending", limit=1000)
        print(f"analyzer pending: {len(pending_an)} (expected {proc})")
        per_paper: list[dict] = []
        while True:
            before = len(usage_log)
            pid_row = await db.fetch_one(
                "SELECT target_id FROM stage_runs WHERE stage='analyzer' AND status='pending' "
                "ORDER BY created_at LIMIT 1"
            )
            s = time.time()
            ok = await analyzer.process_next("bench-an")
            if not ok:
                break
            calls = usage_log[before:]
            per_paper.append({
                "pid": pid_row["target_id"] if pid_row else "?",
                "pages": pages.get(pid_row["target_id"] if pid_row else "", 0),
                "wall": time.time() - s,
                "calls": len(calls),
                "pt": sum(c["pt"] for c in calls),
                "ct": sum(c["ct"] for c in calls),
                "tt": sum(c["tt"] for c in calls),
            })
            p = per_paper[-1]
            print(f"  analyzed {p['pid']} ({p['pages']}p): {p['wall']:.0f}s, "
                  f"{p['calls']} calls, {p['tt']} tok (in {p['pt']}/out {p['ct']})")

        # ---- validation ----
        runs = await db.fetch_all(
            "SELECT paper_id, analysis_basis, score_total, status, tags FROM analysis_runs "
            "WHERE paper_id IN (" + placeholders + ")", tuple(ids)
        )
        failed = await db.fetch_all(
            "SELECT target_id, last_error FROM stage_runs WHERE stage='analyzer' AND status='failed'"
        )

        # ---- report ----
        print("=" * 64)
        if per_paper:
            walls = [p["wall"] for p in per_paper]
            tts = [p["tt"] for p in per_paper]
            tot_in = sum(p["pt"] for p in per_paper)
            tot_out = sum(p["ct"] for p in per_paper)
            cost = (tot_in * args.in_price + tot_out * args.out_price) / 1e6
            print(f"ANALYZER per-paper wall: avg {statistics.mean(walls):.0f}s "
                  f"median {statistics.median(walls):.0f}s min {min(walls):.0f}s max {max(walls):.0f}s")
            print(f"ANALYZER per-paper tokens: avg {statistics.mean(tts):.0f} "
                  f"(in {tot_in//len(per_paper)}/out {tot_out//len(per_paper)})")
            print(f"sample total tokens: in {tot_in} / out {tot_out} / all {tot_in+tot_out}")
            print(f"sample cost @ ${args.in_price}/${args.out_price} per-M (ASSUMED): ${cost:.3f}")
            avg_w = statistics.mean(walls)
            avg_cost = cost / len(per_paper)
            print("-- extrapolation (sequential analyzer) --")
            for label, k in [("120 (have now)", 120), ("780 (6mo wk top-30)", 780), ("1560 (1yr)", 1560)]:
                print(f"  {label}: ~{avg_w*k/3600:.1f} h, ~${avg_cost*k:.1f}")
        print(f"validation: {len(runs)} analysis_runs; "
              f"basis={[r['analysis_basis'] for r in runs]}")
        print(f"scores: {[(r['paper_id'], r['score_total']) for r in runs]}")
        print(f"failed analyzer: {len(failed)}")
        for f in failed:
            print("  FAIL", f["target_id"], "->", (f["last_error"] or "")[:120])
    finally:
        restored = await db.execute(
            "UPDATE stage_runs SET status='pending' WHERE stage='processor' AND status='held_bench'"
        )
        print(f"restored {restored} held processor tasks")
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
