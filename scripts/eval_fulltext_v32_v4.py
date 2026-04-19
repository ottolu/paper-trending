"""Run V3.2 on 20 full-text papers using the v4 peer-review prompt."""
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
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "scripts"))

from backend.analyzer.prompts_v4 import ANALYSIS_SYSTEM_PROMPT as SYSTEM_PROMPT_V4
from eval_fulltext_both import extract_json, score_total, load_papers

load_dotenv(PROJECT / ".env")

RESULTS_PATH = PROJECT / "tests" / "fixtures" / "eval_results_fulltext_v32_v4.json"
MAX_CONCURRENCY = 3
MAX_TOKENS = 6144  # v4 has more narrative fields, allow more tokens


async def call_v32_v4(client: AsyncOpenAI, paper: dict) -> tuple[dict, str]:
    response = await client.chat.completions.create(
        model="deepseek-ai/DeepSeek-V3.2",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_V4},
            {"role": "user", "content": paper["prompt_text"]},
        ],
        temperature=0.0,
        max_tokens=MAX_TOKENS,
        extra_body={"enable_thinking": True, "thinking_budget": 32768},
    )
    msg = response.choices[0].message
    content = msg.content
    if not content or not content.strip():
        content = getattr(msg, "reasoning_content", "") or ""
    if not content.strip():
        raise ValueError("Empty response (content + reasoning_content)")
    return extract_json(content), "siliconflow"


async def analyze(client: AsyncOpenAI, sem: asyncio.Semaphore, paper: dict) -> dict:
    async with sem:
        t0 = time.perf_counter()
        parsed, source = await call_v32_v4(client, paper)
        elapsed = round(time.perf_counter() - t0, 2)
        total = score_total(parsed)
        sb = parsed["score_breakdown"]
        rating = parsed.get("overall_rating", "?")
        print(f"[v4 {paper['idx']:02d}] {paper['arxiv_id']} in {elapsed}s -> "
              f"N{sb['novelty']} R{sb['rigor']} I{sb['impact']} C{sb['clarity']} = {total} | {rating}")
        return {
            "idx": paper["idx"],
            "arxiv_id": paper["arxiv_id"],
            "title": paper["title"],
            "hf_likes": paper["hf_likes"],
            "pages": paper["pages"],
            "prompt_file": paper["prompt_file"],
            "prompt_chars": len(paper["prompt_text"]),
            "model": "deepseek-ai/DeepSeek-V3.2",
            "prompt_version": "v4_peer_review",
            "source": source,
            "elapsed_seconds": elapsed,
            **parsed,
            "score_total": total,
        }


async def main():
    papers = load_papers()
    print(f"Loaded {len(papers)} papers. Total prompt chars: {sum(len(p['prompt_text']) for p in papers):,}")

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
    failed = [(i, r) for i, r in enumerate(results) if isinstance(r, Exception)]
    for i, exc in failed:
        print(f"  [ERR idx={papers[i]['idx']}] {type(exc).__name__}: {str(exc)[:200]}")

    success.sort(key=lambda x: x["idx"])
    RESULTS_PATH.write_text(json.dumps(success, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] {len(success)}/{len(papers)} in {elapsed}s -> {RESULTS_PATH.relative_to(PROJECT)}")


if __name__ == "__main__":
    asyncio.run(main())
