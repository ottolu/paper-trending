"""Cross-model evaluation — use GPT-5.4 via codex to score papers."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import statistics
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.analyzer.prompts_v3 import ANALYSIS_SYSTEM_PROMPT

PAPERS_PATH = Path("/tmp/cross_model_papers_full.json")
RESULTS_DIR = Path("/Users/luotto/paper-trending/data/eval_results")


def build_codex_prompt(paper: dict) -> str:
    authors = ", ".join(paper.get("authors", []))
    categories = ", ".join(paper.get("categories", []))

    return f"""{ANALYSIS_SYSTEM_PROMPT}

---

Now analyze this paper:

# Paper: {paper['title']}
Authors: {authors}
Categories: {categories}
Analysis basis: abstract_only

## Abstract
{paper['abstract']}

Note: Only abstract is available. Assess rigor conservatively but still differentiate — a paper that describes thorough experiments in its abstract can score higher than one that doesn't. Set confidence between 0.3-0.5.

Output ONLY the JSON object, nothing else."""


def run_codex(prompt: str, paper_id: str) -> dict | None:
    """Call codex exec with GPT-5.4 and parse JSON result."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(prompt)
        prompt_file = f.name

    try:
        result = subprocess.run(
            [
                "codex", "exec",
                "-s", "read-only",
                "-c", 'model_reasoning_effort="high"',
                "--json",
            ],
            stdin=open(prompt_file),
            capture_output=True,
            text=True,
            timeout=120,
        )

        # Parse JSONL output to extract agent message
        response_text = ""
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                if obj.get("type") == "item.completed":
                    item = obj.get("item", {})
                    if item.get("type") == "agent_message" and item.get("text"):
                        response_text = item["text"]
            except json.JSONDecodeError:
                continue

        if not response_text:
            print(f"  [{paper_id}] No response text from codex")
            return None

        # Extract JSON from response
        from backend.core.llm_client import _extract_json
        analysis = _extract_json(response_text)
        return analysis

    except subprocess.TimeoutExpired:
        print(f"  [{paper_id}] Codex timed out")
        return None
    except Exception as e:
        print(f"  [{paper_id}] Error: {e}")
        return None
    finally:
        os.unlink(prompt_file)


def spearman(x, y):
    n = len(x)
    if n < 3:
        return 0.0
    def ranks(vals):
        indexed = sorted(enumerate(vals), key=lambda t: t[1])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j < n - 1 and indexed[j+1][1] == indexed[j][1]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[indexed[k][0]] = avg
            i = j + 1
        return r
    rx, ry = ranks(x), ranks(y)
    d_sq = sum((a - b) ** 2 for a, b in zip(rx, ry))
    return round(1 - (6 * d_sq) / (n * (n**2 - 1)), 4)


def main():
    papers = json.loads(PAPERS_PATH.read_text())
    results = []

    print(f"Evaluating {len(papers)} papers with GPT-5.4 via codex...\n")

    for i, paper in enumerate(papers):
        print(f"[{i+1}/{len(papers)}] {paper['id']} ({paper['likes']} likes) — {paper['title'][:50]}...")
        prompt = build_codex_prompt(paper)
        analysis = run_codex(prompt, paper["id"])

        if analysis:
            # Compute score_total from breakdown
            bd = analysis.get("score_breakdown", {})
            vals = [v for v in bd.values() if isinstance(v, (int, float))]
            score_total = round(sum(vals) / len(vals), 2) if vals else 0

            results.append({
                "id": paper["id"],
                "likes": paper["likes"],
                "title": paper["title"],
                "score_total": score_total,
                "score_breakdown": bd,
                "confidence": analysis.get("confidence"),
                "tags": analysis.get("tags"),
                "weaknesses": analysis.get("weaknesses"),
                "factual_summary": analysis.get("factual_summary"),
            })
            print(f"  Score: {score_total} | Breakdown: {bd}")
        else:
            print(f"  FAILED")

    # Metrics
    scores = [r["score_total"] for r in results]
    likes = [r["likes"] for r in results]

    print(f"\n{'='*60}")
    print(f"GPT-5.4 RESULTS ({len(results)}/{len(papers)} papers)")
    print(f"{'='*60}")
    if scores:
        print(f"  Mean: {statistics.mean(scores):.2f}  Stddev: {statistics.stdev(scores):.2f}")
        print(f"  Min: {min(scores)}  Max: {max(scores)}  Range: {max(scores)-min(scores):.2f}")
        print(f"  Spearman vs likes: {spearman(scores, likes)}")

        buckets = {}
        for s in scores:
            b = int(s)
            buckets[b] = buckets.get(b, 0) + 1
        print(f"\n  Distribution:")
        for b in sorted(buckets):
            print(f"    {b}-point: {buckets[b]:3d} {'#' * buckets[b]}")

        for dim in ["novelty", "rigor", "impact", "clarity"]:
            vals = [r["score_breakdown"].get(dim, 0) for r in results if isinstance(r["score_breakdown"], dict)]
            if vals:
                print(f"  {dim:10s}: mean={statistics.mean(vals):.1f} stddev={statistics.stdev(vals):.1f}")

    # Save
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output = {"model": "gpt-5.4", "results": results, "n": len(results)}
    out_path = RESULTS_DIR / "cross_model_gpt54.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
