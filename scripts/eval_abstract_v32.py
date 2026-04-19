"""Run V3.2 analysis on abstract-only prompts for all 20 papers."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "scripts"))
from eval_fulltext_both import SYSTEM_PROMPT, call_v32, score_total  # noqa

load_dotenv(PROJECT / ".env")

INDEX_PATH = PROJECT / "tests" / "fixtures" / "eval_paper_abstract_index.json"
RESULTS_PATH = PROJECT / "tests" / "fixtures" / "eval_results_abstract_v32.json"
MAX_CONCURRENCY = 3


def load_papers() -> list[dict]:
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    papers = []
    for item in index:
        path = PROJECT / item["prompt_file"]
        papers.append({
            "idx": item["idx"],
            "arxiv_id": item["arxiv_id"],
            "title": item["title"],
            "hf_likes": item.get("hf_likes", 0),
            "pages": item.get("pages", 0),
            "prompt_file": item["prompt_file"],
            "prompt_text": path.read_text(encoding="utf-8"),
        })
    return sorted(papers, key=lambda p: p["idx"])


async def analyze(client: AsyncOpenAI, sem: asyncio.Semaphore, paper: dict) -> dict:
    async with sem:
        t0 = time.perf_counter()
        parsed, source = await call_v32(client, paper)
        elapsed = round(time.perf_counter() - t0, 2)
        total = score_total(parsed)
        sb = parsed["score_breakdown"]
        print(f"[abs {paper['idx']:02d}] {paper['arxiv_id']} in {elapsed}s -> "
              f"N{sb['novelty']} R{sb['rigor']} I{sb['impact']} C{sb['clarity']} = {total}")
        return {
            "idx": paper["idx"],
            "arxiv_id": paper["arxiv_id"],
            "title": paper["title"],
            "hf_likes": paper["hf_likes"],
            "pages": paper["pages"],
            "prompt_file": paper["prompt_file"],
            "prompt_chars": len(paper["prompt_text"]),
            "model": "deepseek-ai/DeepSeek-V3.2",
            "source": source,
            "elapsed_seconds": elapsed,
            **parsed,
            "score_total": total,
        }


async def main():
    papers = load_papers()
    print(f"Loaded {len(papers)} abstract prompts. Total chars: {sum(len(p['prompt_text']) for p in papers):,}")

    client = AsyncOpenAI(
        base_url="https://api.siliconflow.cn/v1",
        api_key=os.environ["SILICONFLOW_API_KEY"],
    )
    sem = asyncio.Semaphore(MAX_CONCURRENCY)

    t0 = time.perf_counter()
    results = await asyncio.gather(
        *[analyze(client, sem, p) for p in papers], return_exceptions=True
    )
    elapsed = round(time.perf_counter() - t0, 2)

    success = [r for r in results if not isinstance(r, Exception)]
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            print(f"  [ERR idx={papers[i]['idx']}] {type(r).__name__}: {str(r)[:200]}")

    success.sort(key=lambda x: x["idx"])
    RESULTS_PATH.write_text(json.dumps(success, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] {len(success)}/{len(papers)} in {elapsed}s -> {RESULTS_PATH.relative_to(PROJECT)}")


if __name__ == "__main__":
    asyncio.run(main())
