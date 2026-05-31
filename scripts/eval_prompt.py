"""Prompt evaluation harness — run analyzer on test set and compute metrics.

Usage:
    python scripts/eval_prompt.py [--round N] [--held-out] [--max-concurrent 5] [--prompt-version v1|v2]

Outputs metrics to data/eval_results/round_N.json
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.core.database import Database
from backend.core.llm_client import LLMClient

# Prompt version registry
PROMPT_VERSIONS = {}


def _load_prompt_version(version: str):
    # `prompts.py` is the single production prompt (fulltext-aware v3).
    # Numbered files only exist as historical eval baselines; delete when
    # no longer needed for reproducibility.
    if version in ("v1", "v3", "current", "production"):
        from backend.analyzer.prompts import ANALYSIS_SYSTEM_PROMPT, build_analysis_prompt
    elif version == "v2":
        from backend.analyzer.prompts_v2 import ANALYSIS_SYSTEM_PROMPT, build_analysis_prompt
    elif version == "v4":
        from backend.analyzer.prompts_v4 import ANALYSIS_SYSTEM_PROMPT, build_analysis_prompt
    else:
        raise ValueError(f"Unknown prompt version: {version}")
    return ANALYSIS_SYSTEM_PROMPT, build_analysis_prompt


# Global state set by main()
_current_build_prompt = None
_current_system_prompt = None
_current_version = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("eval")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = PROJECT_ROOT / "data"
DB_PATH = str(DATA_ROOT / "tracker.db")
PAPER_ROOT = str(DATA_ROOT / "papers")
TEST_SET_PATH = DATA_ROOT / "eval_test_set.json"
RESULTS_DIR = DATA_ROOT / "eval_results"

SF_BASE_URL = "https://api.siliconflow.cn/v1"
SF_API_KEY = os.environ["SILICONFLOW_API_KEY"]
LLM_MODEL = "Qwen/Qwen3-VL-235B-A22B-Thinking"
EMBED_MODEL = "Qwen/Qwen3-Embedding-8B"


async def analyze_paper(llm: LLMClient, paper_id: str, db: Database) -> dict | None:
    """Run analysis on a single paper, return the raw LLM output dict."""
    paper = await db.fetch_one("SELECT * FROM papers WHERE id = ?", (paper_id,))
    if not paper:
        logger.warning("Paper %s not found", paper_id)
        return None

    authors = json.loads(paper["authors"]) if paper["authors"] else []
    categories = json.loads(paper["arxiv_categories"]) if paper["arxiv_categories"] else []

    manifest = {
        "paper_id": paper_id,
        "title": paper["title"],
        "abstract": paper["abstract"],
        "authors": authors,
        "arxiv_categories": categories,
        "published_date": paper["published_date"],
        "analysis_basis": "abstract_only",
        "chunks": [],
        "sections": [],
    }

    messages = _current_build_prompt(manifest)
    try:
        analysis = await llm.chat_json(messages, temperature=0)
        analysis["_paper_id"] = paper_id
        analysis["_title"] = paper["title"]
        return analysis
    except Exception as e:
        logger.error("Failed to analyze %s: %s", paper_id, e)
        return None


async def run_eval(
    paper_ids: list[str],
    likes_map: dict[str, int],
    round_name: str,
    max_concurrent: int = 5,
) -> dict:
    """Run eval on a list of paper IDs and compute metrics."""
    db = Database(DB_PATH)
    await db.initialize()
    llm = LLMClient(base_url=SF_BASE_URL, api_key=SF_API_KEY, model=LLM_MODEL)

    sem = asyncio.Semaphore(max_concurrent)
    results = []
    start = time.time()

    async def _bounded(pid):
        async with sem:
            return await analyze_paper(llm, pid, db)

    tasks = [asyncio.create_task(_bounded(pid)) for pid in paper_ids]
    raw_results = await asyncio.gather(*tasks)

    for r in raw_results:
        if r:
            results.append(r)

    elapsed = time.time() - start
    await db.close()

    # --- Compute score_total from breakdown if missing ---
    for r in results:
        if "score_total" not in r or r["score_total"] is None:
            bd = r.get("score_breakdown", {})
            if isinstance(bd, dict):
                vals = [v for v in bd.values() if isinstance(v, (int, float))]
                r["score_total"] = round(sum(vals) / len(vals), 2) if vals else 0

    scores = [r.get("score_total", 0) for r in results]
    likes = [likes_map.get(r["_paper_id"], 0) for r in results]

    metrics = {}
    if scores:
        metrics["n"] = len(scores)
        metrics["score_mean"] = round(statistics.mean(scores), 2)
        metrics["score_stddev"] = round(statistics.stdev(scores), 2) if len(scores) > 1 else 0
        metrics["score_min"] = min(scores)
        metrics["score_max"] = max(scores)
        metrics["score_range"] = round(max(scores) - min(scores), 2)
        metrics["cv"] = round(metrics["score_stddev"] / metrics["score_mean"], 3) if metrics["score_mean"] else 0

        # Score distribution buckets
        buckets = {}
        for s in scores:
            b = int(s)
            buckets[b] = buckets.get(b, 0) + 1
        metrics["score_distribution"] = dict(sorted(buckets.items()))

        # Rank correlation with HF likes (Spearman)
        if len(scores) > 2 and any(lk > 0 for lk in likes):
            metrics["spearman_vs_likes"] = _spearman(scores, likes)
        else:
            metrics["spearman_vs_likes"] = None

        # Sub-score stats
        for dim in ["novelty", "rigor", "impact", "clarity"]:
            vals = []
            for r in results:
                bd = r.get("score_breakdown", {})
                if isinstance(bd, dict) and dim in bd:
                    v = bd[dim]
                    if isinstance(v, (int, float)):
                        vals.append(v)
            if vals:
                metrics[f"{dim}_mean"] = round(statistics.mean(vals), 2)
                metrics[f"{dim}_stddev"] = round(statistics.stdev(vals), 2) if len(vals) > 1 else 0

    metrics["elapsed_seconds"] = round(elapsed, 1)
    metrics["valid_json_rate"] = round(len(results) / len(paper_ids), 3) if paper_ids else 0

    # Prompt hash for versioning
    prompt_hash = hashlib.sha256(_current_system_prompt.encode()).hexdigest()[:12]
    metrics["prompt_hash"] = prompt_hash

    # Save results
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output = {
        "round": round_name,
        "prompt_hash": prompt_hash,
        "metrics": metrics,
        "papers": [
            {
                "id": r["_paper_id"],
                "title": r["_title"],
                "likes": likes_map.get(r["_paper_id"], 0),
                "score_total": r.get("score_total"),
                "score_breakdown": r.get("score_breakdown"),
                "confidence": r.get("confidence"),
                "tags": r.get("tags"),
                "factual_summary": r.get("factual_summary"),
                "innovation_points": r.get("innovation_points"),
                "evidence_level": r.get("evidence_level"),
            }
            for r in results
        ],
    }

    out_path = RESULTS_DIR / f"{round_name}.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    logger.info("Results saved to %s", out_path)

    return metrics


def _spearman(x: list[float], y: list[float]) -> float:
    """Compute Spearman rank correlation coefficient."""
    n = len(x)
    if n < 3:
        return 0.0

    def _ranks(vals):
        indexed = sorted(enumerate(vals), key=lambda t: t[1])
        ranks = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j < n - 1 and indexed[j + 1][1] == indexed[j][1]:
                j += 1
            avg_rank = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                ranks[indexed[k][0]] = avg_rank
            i = j + 1
        return ranks

    rx = _ranks(x)
    ry = _ranks(y)
    d_sq = sum((a - b) ** 2 for a, b in zip(rx, ry))
    return round(1 - (6 * d_sq) / (n * (n**2 - 1)), 4)


def print_metrics(metrics: dict, round_name: str):
    """Pretty-print metrics."""
    print(f"\n{'=' * 60}")
    print(f"  ROUND: {round_name} | Prompt: {metrics.get('prompt_hash', '?')}")
    print(f"{'=' * 60}")
    print(f"  Papers analyzed: {metrics.get('n', 0)} | Time: {metrics.get('elapsed_seconds', 0)}s")
    print(f"  JSON success rate: {metrics.get('valid_json_rate', 0):.1%}")
    print("\n  SCORES:")
    print(f"    Mean: {metrics.get('score_mean', 0):.2f}  Stddev: {metrics.get('score_stddev', 0):.2f}")
    print(f"    Min: {metrics.get('score_min', 0)}  Max: {metrics.get('score_max', 0)}  Range: {metrics.get('score_range', 0)}")
    print(f"    CV: {metrics.get('cv', 0):.3f}")
    print(f"    Spearman vs likes: {metrics.get('spearman_vs_likes', 'N/A')}")

    dist = metrics.get("score_distribution", {})
    if dist:
        print("\n  DISTRIBUTION:")
        for bucket in sorted(dist.keys()):
            bar = "#" * dist[bucket]
            print(f"    {bucket}-point: {dist[bucket]:3d} {bar}")

    print("\n  SUB-SCORES (mean ± stddev):")
    for dim in ["novelty", "rigor", "impact", "clarity"]:
        m = metrics.get(f"{dim}_mean", "?")
        s = metrics.get(f"{dim}_stddev", "?")
        print(f"    {dim:10s}: {m} ± {s}")
    print()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--round", default="r0_baseline", help="Round name for output")
    parser.add_argument("--held-out", action="store_true", help="Run on held-out set instead")
    parser.add_argument("--max-concurrent", type=int, default=5)
    parser.add_argument("--prompt-version", default="v1", choices=["v1", "v2", "v3"])
    args = parser.parse_args()

    global _current_build_prompt, _current_system_prompt, _current_version
    _current_version = args.prompt_version
    _current_system_prompt, _current_build_prompt = _load_prompt_version(args.prompt_version)

    test_data = json.loads(TEST_SET_PATH.read_text())
    key = "held_out" if args.held_out else "test_set"
    papers = test_data[key]
    paper_ids = [p["id"] for p in papers]
    likes_map = {p["id"]: p["likes"] for p in papers}

    logger.info("Running eval round '%s' on %d papers (%s)", args.round, len(paper_ids), key)
    metrics = await run_eval(paper_ids, likes_map, args.round, args.max_concurrent)
    print_metrics(metrics, args.round)


if __name__ == "__main__":
    asyncio.run(main())
