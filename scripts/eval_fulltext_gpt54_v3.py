"""Run GPT-5.4 via codex exec on 20 full-text papers using v3 (current) prompt."""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "scripts"))
from eval_fulltext_both import SYSTEM_PROMPT as SYSTEM_PROMPT_V3, extract_json, score_total, load_papers

RESULTS_PATH = PROJECT / "tests" / "fixtures" / "eval_results_fulltext_gpt54.json"
MAX_CONCURRENCY = 2


async def codex_exec(paper: dict) -> tuple[dict, str]:
    fallback_prompt = (
        f"{SYSTEM_PROMPT_V3}\n\n"
        "Paper prompt follows. Return only the JSON object, no markdown fences.\n\n"
        f"{paper['prompt_text']}"
    )
    output_path = PROJECT / f".tmp_codex_v3_out_{paper['idx']}.json"
    if output_path.exists():
        output_path.unlink()

    process = await asyncio.create_subprocess_exec(
        "codex", "exec",
        "--model", "gpt-5.4",
        "--color", "never",
        "--ephemeral",
        "--output-last-message", str(output_path),
        "-",
        cwd=str(PROJECT),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate(fallback_prompt.encode("utf-8"))
    if process.returncode != 0:
        raise RuntimeError(
            f"codex exec failed: exit={process.returncode}, "
            f"stderr={stderr.decode('utf-8', errors='ignore')[:500]}"
        )
    if not output_path.exists():
        raise RuntimeError("codex exec did not produce output file")
    try:
        raw = output_path.read_text(encoding="utf-8")
        return extract_json(raw), "codex_exec"
    finally:
        output_path.unlink(missing_ok=True)


async def analyze(sem: asyncio.Semaphore, paper: dict) -> dict:
    async with sem:
        t0 = time.perf_counter()
        parsed, source = await codex_exec(paper)
        elapsed = round(time.perf_counter() - t0, 2)
        total = score_total(parsed)
        sb = parsed["score_breakdown"]
        print(f"[gpt54 v3 {paper['idx']:02d}] {paper['arxiv_id']} in {elapsed}s -> "
              f"N{sb['novelty']} R{sb['rigor']} I{sb['impact']} C{sb['clarity']} = {total}",
              flush=True)
        return {
            "idx": paper["idx"],
            "arxiv_id": paper["arxiv_id"],
            "title": paper["title"],
            "hf_likes": paper["hf_likes"],
            "pages": paper["pages"],
            "prompt_file": paper["prompt_file"],
            "prompt_chars": len(paper["prompt_text"]),
            "model": "gpt-5.4",
            "prompt_version": "v3_current",
            "source": source,
            "elapsed_seconds": elapsed,
            **parsed,
            "score_total": total,
        }


async def main():
    papers = load_papers()
    print(f"Loaded {len(papers)} papers. Total prompt chars: {sum(len(p['prompt_text']) for p in papers):,}",
          flush=True)

    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    t0 = time.perf_counter()
    results = await asyncio.gather(
        *[analyze(sem, p) for p in papers], return_exceptions=True
    )
    elapsed = round(time.perf_counter() - t0, 2)

    success = [r for r in results if not isinstance(r, Exception)]
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            print(f"  [ERR idx={papers[i]['idx']}] {type(r).__name__}: {str(r)[:200]}", flush=True)

    success.sort(key=lambda x: x["idx"])
    RESULTS_PATH.write_text(json.dumps(success, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] {len(success)}/{len(papers)} in {elapsed}s -> {RESULTS_PATH.relative_to(PROJECT)}",
          flush=True)


if __name__ == "__main__":
    asyncio.run(main())
