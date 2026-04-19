"""Retry V3.2 for idx=10 and merge into eval_results_fulltext_v32.json."""
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
from eval_fulltext_both import SYSTEM_PROMPT, call_v32, score_total, load_papers  # noqa

load_dotenv(PROJECT / ".env")

RESULTS_PATH = PROJECT / "tests" / "fixtures" / "eval_results_fulltext_v32.json"


async def main():
    papers = load_papers()
    paper = next(p for p in papers if p["idx"] == 10)
    print(f"Retrying [{paper['idx']}] {paper['arxiv_id']}: {paper['title'][:60]}")
    print(f"Prompt chars: {len(paper['prompt_text']):,}")

    client = AsyncOpenAI(
        base_url="https://api.siliconflow.cn/v1",
        api_key=os.environ["SILICONFLOW_API_KEY"],
    )

    t0 = time.perf_counter()
    parsed, source = await call_v32(client, paper)
    elapsed = round(time.perf_counter() - t0, 2)
    total = score_total(parsed)

    result = {
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
    sb = parsed["score_breakdown"]
    print(f"[V3.2 10] via {source} in {elapsed}s -> "
          f"N{sb['novelty']} R{sb['rigor']} I{sb['impact']} C{sb['clarity']} = {total}")

    existing = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    existing = [r for r in existing if r["idx"] != 10]
    existing.append(result)
    existing.sort(key=lambda x: x["idx"])

    RESULTS_PATH.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Merged. Total results: {len(existing)}")


if __name__ == "__main__":
    asyncio.run(main())
