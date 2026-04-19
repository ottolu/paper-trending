"""Run V3.2 and GPT-5.4 analysis on 20 papers with COMPLETE full text (no truncation).

Uses tests/fixtures/eval_paper_fulltext_*.txt prompts built from PyMuPDF full extraction.

Outputs:
  tests/fixtures/eval_results_fulltext_v32.json
  tests/fixtures/eval_results_fulltext_gpt54.json
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI, RateLimitError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
INDEX_PATH = FIXTURES_DIR / "eval_paper_fulltext_index.json"
AUTH_PATH = Path.home() / ".codex" / "auth.json"

MAX_CONCURRENCY = 3
MAX_TOKENS = 4096

load_dotenv(PROJECT_ROOT / ".env")

SYSTEM_PROMPT = """You are an expert AI research paper analyst. Critically evaluate the paper and produce a calibrated assessment that differentiates quality levels.

Think through your analysis carefully, then output a single JSON object.

## Scoring Rubric

Each dimension is scored 1-10. Use the FULL range — your scores should spread across papers, not cluster.

**novelty** (How new is this?)
- 2-3: Applies known methods to a new dataset/domain, or minor variation of existing work
- 4-5: Meaningful combination of existing ideas, useful but not surprising
- 6-7: New perspective, method, or framework with clear differentiation from prior work
- 8-9: Fundamentally new idea that opens a research direction
- 10: Paradigm-shifting

**rigor** (How solid is the evidence?)
- 2-3: Claims not well-supported, missing key comparisons
- 4-5: Standard evaluation, limited scope, some gaps
- 6-7: Solid experiments with proper baselines and ablations
- 8-9: Comprehensive evaluation across multiple settings
- 10: Gold-standard evaluation methodology

**impact** (How much will this matter in 2 years?)
- 2-3: Very narrow audience
- 4-5: Useful to practitioners in one area
- 6-7: Broadly applicable, will influence multiple groups
- 8-9: Will be widely adopted or spark major follow-up work
- 10: Will change industry practice or redirect a field

**clarity** (How well is it communicated?)
- 2-3: Hard to follow, missing key details
- 4-5: Understandable but requires effort
- 6-7: Well-structured, clear, reproducible
- 8-9: Exceptionally well-written, comprehensive
- 10: Textbook example of scientific writing

## Important Scoring Rules
1. DIFFERENTIATE: Some papers are 3s, some are 8s. Use the full range.
2. WEAKNESSES FIRST: Identify flaws before scoring.
3. COMPARE TO BASELINE: Known method applied = 4-5 on novelty, not 6-7.
4. HIGH SCORES NEED JUSTIFICATION: 8+ needs specific evidence.

## Output Schema
Required JSON fields:
- weaknesses: list[string] — at least 2
- factual_summary: string — 2-3 sentences
- methodology_inference: string
- innovation_points: list[string]
- key_takeaways: list[string] — 3-5 points
- score_breakdown: {"novelty": int, "rigor": int, "impact": int, "clarity": int}
- tags: list[string] — 5-8 tags
- evidence_level: "strong" | "moderate" | "limited"
- confidence: float 0-1

Do NOT include score_total.
"""


def load_papers() -> list[dict]:
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    papers: list[dict] = []
    for item in index:
        prompt_path = PROJECT_ROOT / item["prompt_file"]
        papers.append({
            "idx": item["idx"],
            "arxiv_id": item["arxiv_id"],
            "title": item["title"],
            "hf_likes": item.get("hf_likes", 0),
            "pages": item.get("pages", 0),
            "prompt_file": item["prompt_file"],
            "prompt_text": prompt_path.read_text(encoding="utf-8"),
        })
    return sorted(papers, key=lambda p: p["idx"])


def extract_json(raw_text: str) -> dict:
    text = raw_text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found")
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if esc:
            esc = False
            continue
        if ch == "\\" and in_str:
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("Incomplete JSON")


def score_total(parsed: dict) -> int:
    sb = parsed.get("score_breakdown", {})
    vals = [sb.get("novelty"), sb.get("rigor"), sb.get("impact"), sb.get("clarity")]
    if any(not isinstance(v, int) for v in vals):
        raise ValueError(f"Bad score_breakdown: {sb}")
    return sum(vals)


# --- DeepSeek V3.2 via SiliconFlow ---

async def call_v32(client: AsyncOpenAI, paper: dict) -> tuple[dict, str]:
    response = await client.chat.completions.create(
        model="deepseek-ai/DeepSeek-V3.2",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": paper["prompt_text"]},
        ],
        temperature=0.0,
        max_tokens=MAX_TOKENS,
        extra_body={"enable_thinking": True, "thinking_budget": 32768},
    )
    msg = response.choices[0].message
    content = msg.content
    # Fallback: V3.2 sometimes emits the final JSON into reasoning_content
    if not content or not content.strip():
        content = getattr(msg, "reasoning_content", "") or ""
    if not content.strip():
        raise ValueError("Empty V3.2 response (content and reasoning_content both empty)")
    return extract_json(content), "siliconflow"


# --- GPT-5.4 via codex ---

def load_codex_token() -> str:
    auth = json.loads(AUTH_PATH.read_text(encoding="utf-8"))
    token = auth.get("tokens", {}).get("access_token")
    if not token:
        raise RuntimeError(f"Missing tokens.access_token in {AUTH_PATH}")
    return token


async def call_gpt54_api(client: AsyncOpenAI, paper: dict) -> tuple[dict, str]:
    response = await client.chat.completions.create(
        model="gpt-5.4",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": paper["prompt_text"]},
        ],
        temperature=0,
        max_tokens=MAX_TOKENS,
        reasoning_effort="high",
    )
    content = response.choices[0].message.content
    if not content or not content.strip():
        raise ValueError("Empty GPT-5.4 response")
    return extract_json(content), "openai_api"


async def codex_exec_fallback(paper: dict) -> tuple[dict, str]:
    fallback_prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        "Paper prompt follows. Return only the JSON object, with no markdown fences.\n\n"
        f"{paper['prompt_text']}"
    )
    output_path = PROJECT_ROOT / f".tmp_codex_output_{paper['idx']}.json"
    if output_path.exists():
        output_path.unlink()

    process = await asyncio.create_subprocess_exec(
        "codex", "exec",
        "--model", "gpt-5.4",
        "--color", "never",
        "--ephemeral",
        "--output-last-message", str(output_path),
        "-",
        cwd=str(PROJECT_ROOT),
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


# --- Runner ---

async def analyze_v32(client: AsyncOpenAI, sem: asyncio.Semaphore, paper: dict) -> dict:
    async with sem:
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
        print(f"[V3.2 {paper['idx']:02d}] {paper['arxiv_id']} via {source} in {elapsed}s "
              f"-> N{sb['novelty']} R{sb['rigor']} I{sb['impact']} C{sb['clarity']} = {total}")
        return result


async def analyze_gpt54(client: AsyncOpenAI, sem: asyncio.Semaphore, paper: dict) -> dict:
    async with sem:
        t0 = time.perf_counter()
        try:
            parsed, source = await call_gpt54_api(client, paper)
        except RateLimitError:
            parsed, source = await codex_exec_fallback(paper)
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            if status == 429:
                parsed, source = await codex_exec_fallback(paper)
            else:
                raise
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
            "model": "gpt-5.4",
            "source": source,
            "elapsed_seconds": elapsed,
            **parsed,
            "score_total": total,
        }
        sb = parsed["score_breakdown"]
        print(f"[GPT 5.4 {paper['idx']:02d}] {paper['arxiv_id']} via {source} in {elapsed}s "
              f"-> N{sb['novelty']} R{sb['rigor']} I{sb['impact']} C{sb['clarity']} = {total}")
        return result


async def run_model(model: str, papers: list[dict]) -> list[dict]:
    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    if model == "v32":
        api_key = os.environ.get("SILICONFLOW_API_KEY")
        if not api_key:
            raise RuntimeError("SILICONFLOW_API_KEY not set")
        client = AsyncOpenAI(base_url="https://api.siliconflow.cn/v1", api_key=api_key)
        tasks = [analyze_v32(client, sem, p) for p in papers]
    else:
        token = load_codex_token()
        client = AsyncOpenAI(api_key=token)
        tasks = [analyze_gpt54(client, sem, p) for p in papers]

    t0 = time.perf_counter()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = round(time.perf_counter() - t0, 2)

    success = [r for r in results if not isinstance(r, Exception)]
    failed = [(i, r) for i, r in enumerate(results) if isinstance(r, Exception)]
    for i, exc in failed:
        print(f"  [ERR {model} idx={papers[i]['idx']}] {type(exc).__name__}: {str(exc)[:200]}")

    success.sort(key=lambda x: x["idx"])
    print(f"\n[{model}] Completed {len(success)}/{len(papers)} in {elapsed}s")
    return success


async def main() -> None:
    papers = load_papers()
    print(f"Loaded {len(papers)} papers. Total prompt chars: {sum(len(p['prompt_text']) for p in papers):,}")

    which = sys.argv[1] if len(sys.argv) > 1 else "both"

    if which in ("both", "v32"):
        print("\n=== Running DeepSeek V3.2 (SiliconFlow) ===")
        v32_results = await run_model("v32", papers)
        out = FIXTURES_DIR / "eval_results_fulltext_v32.json"
        out.write_text(json.dumps(v32_results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[v32] Saved {len(v32_results)} results to {out.relative_to(PROJECT_ROOT)}")

    if which in ("both", "gpt54"):
        print("\n=== Running GPT-5.4 ===")
        gpt_results = await run_model("gpt54", papers)
        out = FIXTURES_DIR / "eval_results_fulltext_gpt54.json"
        out.write_text(json.dumps(gpt_results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[gpt54] Saved {len(gpt_results)} results to {out.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
