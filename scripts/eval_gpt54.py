from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from pathlib import Path

from openai import AsyncOpenAI, RateLimitError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
AUTH_PATH = Path.home() / ".codex" / "auth.json"
INDEX_PATH = FIXTURES_DIR / "eval_paper_index.json"
OUTPUT_PATH = FIXTURES_DIR / "eval_results_gpt54.json"
MODEL_NAME = "gpt-5.4"
MAX_CONCURRENCY = 3
MAX_TOKENS = 4096

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


def load_access_token() -> str:
    auth = json.loads(AUTH_PATH.read_text(encoding="utf-8"))
    token = auth.get("tokens", {}).get("access_token")
    if not token:
        raise RuntimeError(f"Missing tokens.access_token in {AUTH_PATH}")
    return token


def load_papers() -> list[dict]:
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    papers: list[dict] = []
    for item in index:
        idx = item["idx"]
        prompt_path = FIXTURES_DIR / f"eval_paper_{idx}.txt"
        papers.append(
            {
                "idx": idx,
                "arxiv_id": item["arxiv_id"],
                "title": item["title"],
                "hf_likes": item.get("hf_likes", 0),
                "prompt_file": str(prompt_path.relative_to(PROJECT_ROOT)),
                "prompt_text": prompt_path.read_text(encoding="utf-8"),
            }
        )
    return sorted(papers, key=lambda paper: paper["idx"])


def extract_json(raw_text: str) -> dict:
    text = raw_text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in model output")

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        ch = text[index]
        if escaped:
            escaped = False
            continue
        if ch == "\\" and in_string:
            escaped = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : index + 1])

    raise ValueError("Incomplete JSON object in model output")


def build_messages(prompt_text: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt_text},
    ]


def score_total_from_result(result: dict) -> int:
    score_breakdown = result.get("score_breakdown", {})
    values = [
        score_breakdown.get("novelty"),
        score_breakdown.get("rigor"),
        score_breakdown.get("impact"),
        score_breakdown.get("clarity"),
    ]
    if any(not isinstance(value, int) for value in values):
        raise ValueError(f"Invalid score_breakdown: {score_breakdown}")
    return sum(values)


async def codex_exec_fallback(paper: dict) -> tuple[dict, str]:
    fallback_prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        "Paper prompt follows. Return only the JSON object, with no markdown fences.\n\n"
        f"{paper['prompt_text']}"
    )
    output_path = PROJECT_ROOT / f".tmp_codex_eval_output_{paper['idx']}.json"
    if output_path.exists():
        output_path.unlink()

    process = await asyncio.create_subprocess_exec(
        "codex",
        "exec",
        "--model",
        MODEL_NAME,
        "--color",
        "never",
        "--ephemeral",
        "--output-last-message",
        str(output_path),
        "-",
        cwd=str(PROJECT_ROOT),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate(fallback_prompt.encode("utf-8"))
    if process.returncode != 0:
        raise RuntimeError(
            "codex exec fallback failed: "
            f"exit={process.returncode}, stdout={stdout.decode('utf-8', errors='ignore')}, "
            f"stderr={stderr.decode('utf-8', errors='ignore')}"
        )
    if not output_path.exists():
        raise RuntimeError("codex exec fallback did not produce an output file")
    try:
        raw = output_path.read_text(encoding="utf-8")
        parsed = extract_json(raw)
        return parsed, "codex_exec"
    finally:
        output_path.unlink(missing_ok=True)


async def call_openai_api(client: AsyncOpenAI, paper: dict) -> tuple[dict, str]:
    response = await client.chat.completions.create(
        model=MODEL_NAME,
        messages=build_messages(paper["prompt_text"]),
        temperature=0,
        max_tokens=MAX_TOKENS,
        reasoning_effort="high",
    )
    content = response.choices[0].message.content
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Empty response content from OpenAI API")
    return extract_json(content), "openai_api"


async def analyze_one(client: AsyncOpenAI, sem: asyncio.Semaphore, paper: dict) -> dict:
    async with sem:
        started_at = time.perf_counter()
        try:
            parsed, source = await call_openai_api(client, paper)
        except RateLimitError:
            parsed, source = await codex_exec_fallback(paper)
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            if status_code == 429:
                parsed, source = await codex_exec_fallback(paper)
            else:
                raise

        elapsed_seconds = round(time.perf_counter() - started_at, 2)
        score_total = score_total_from_result(parsed)
        result = {
            "idx": paper["idx"],
            "arxiv_id": paper["arxiv_id"],
            "title": paper["title"],
            "hf_likes": paper["hf_likes"],
            "prompt_file": paper["prompt_file"],
            "model": MODEL_NAME,
            "source": source,
            "elapsed_seconds": elapsed_seconds,
            **parsed,
            "score_total": score_total,
        }
        print(
            f"[{paper['idx']:02d}] {paper['arxiv_id']} via {source} "
            f"in {elapsed_seconds:.2f}s -> total={score_total}"
        )
        return result


async def main() -> None:
    access_token = load_access_token()
    papers = load_papers()
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    client = AsyncOpenAI(api_key=access_token)

    started_at = time.perf_counter()
    tasks = [analyze_one(client, semaphore, paper) for paper in papers]
    results = await asyncio.gather(*tasks)
    results.sort(key=lambda item: item["idx"])
    OUTPUT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    elapsed_seconds = round(time.perf_counter() - started_at, 2)
    print(f"Saved {len(results)} results to {OUTPUT_PATH.relative_to(PROJECT_ROOT)} in {elapsed_seconds:.2f}s")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
