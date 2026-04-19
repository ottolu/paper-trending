"""Retry idx=8 for GPT-5.4 v4 and merge into results."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "scripts"))
from eval_fulltext_gpt54_v4 import analyze

from eval_fulltext_both import load_papers

RESULTS_PATH = PROJECT / "tests" / "fixtures" / "eval_results_fulltext_gpt54_v4.json"


async def main():
    papers = load_papers()
    paper = next(p for p in papers if p["idx"] == 8)
    print(f"Retrying [{paper['idx']:02d}] {paper['arxiv_id']}: {paper['title'][:60]}")

    sem = asyncio.Semaphore(1)
    result = await analyze(sem, paper)

    existing = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    existing = [r for r in existing if r["idx"] != 8]
    existing.append(result)
    existing.sort(key=lambda x: x["idx"])
    RESULTS_PATH.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Merged. Total: {len(existing)}")


if __name__ == "__main__":
    asyncio.run(main())
