"""Cross-model full-text evaluation — GPT-5.4 via codex on the same 20 papers."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import statistics
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.analyzer.prompts import ANALYSIS_SYSTEM_PROMPT

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"
RESULTS_DIR = DATA_ROOT / "eval_results"


def build_codex_prompt(manifest: dict, markdown_path: str) -> str:
    title = manifest["title"]
    abstract = manifest["abstract"]
    authors = ", ".join(manifest.get("authors", []))
    categories = ", ".join(manifest.get("arxiv_categories", []))

    return f"""{ANALYSIS_SYSTEM_PROMPT}

---

Now analyze this paper. The full text is available as a markdown file — read it first.

# Paper: {title}
Authors: {authors}
Categories: {categories}

## Abstract
{abstract}

## Full Text
Read the full paper markdown from: {markdown_path}

After reading the full text, output ONLY the JSON object, nothing else."""


def run_codex(prompt: str, paper_id: str) -> dict | None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(prompt)
        prompt_file = f.name

    try:
        result = subprocess.run(
            f"cat {prompt_file} | codex exec -s read-only "
            f"-c 'model_reasoning_effort=\"high\"' --json",
            shell=True,
            capture_output=True, text=True, timeout=180,
        )

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
            return None

        from backend.core.llm_client import _extract_json
        return _extract_json(response_text)

    except subprocess.TimeoutExpired:
        print(f"  [{paper_id}] Timeout")
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
    import sqlite3

    c = sqlite3.connect(str(DATA_ROOT / "tracker.db"))
    rows = c.execute("""
        SELECT ar.paper_id, ar.chunk_manifest_path, ps.hf_likes, p.title,
               pe.extracted_markdown_path
        FROM analysis_runs ar
        JOIN papers p ON ar.paper_id = p.id
        LEFT JOIN paper_sources ps ON ar.paper_id = ps.paper_id AND ps.source_name = 'huggingface'
        LEFT JOIN pdf_extractions pe ON ar.paper_id = pe.paper_id AND pe.extraction_status = 'succeeded'
        WHERE ar.status = 'succeeded' AND ar.analysis_basis = 'full_text'
        ORDER BY ps.hf_likes DESC
    """).fetchall()
    c.close()

    print(f"Evaluating {len(rows)} full-text papers with GPT-5.4 via codex...\n")

    results = []
    for i, (pid, manifest_path, likes, title, md_path) in enumerate(rows):
        print(f"[{i+1}/{len(rows)}] {pid} ({likes or 0}L) — {title[:50]}...")
        manifest = json.loads(Path(manifest_path).read_text())
        abs_md_path = str(Path(md_path).resolve()) if md_path else ""
        prompt = build_codex_prompt(manifest, abs_md_path)
        print(f"  Prompt: {len(prompt)} chars | MD: {abs_md_path}")

        analysis = run_codex(prompt, pid)
        if analysis:
            bd = analysis.get("score_breakdown", {})
            vals = [v for v in bd.values() if isinstance(v, (int, float))]
            score = round(sum(vals) / len(vals), 2) if vals else 0
            results.append({
                "id": pid, "likes": likes or 0, "title": title,
                "score_total": score, "score_breakdown": bd,
                "confidence": analysis.get("confidence"),
            })
            print(f"  Score: {score} | {bd}")
        else:
            print("  FAILED")

        time.sleep(2)  # Be gentle

    # Stats
    scores = [r["score_total"] for r in results]
    likes_list = [r["likes"] for r in results]

    print(f"\n{'='*60}")
    print(f"GPT-5.4 FULL-TEXT RESULTS ({len(results)}/{len(rows)} papers)")
    print(f"{'='*60}")
    if len(scores) > 2:
        print(f"  Mean: {statistics.mean(scores):.2f}  Stddev: {statistics.stdev(scores):.2f}")
        print(f"  Min: {min(scores)}  Max: {max(scores)}  Range: {max(scores)-min(scores):.2f}")
        print(f"  Spearman vs likes: {spearman(scores, likes_list)}")

        buckets = {}
        for s in scores:
            b = int(s)
            buckets[b] = buckets.get(b, 0) + 1
        print("\n  Distribution:")
        for b in sorted(buckets):
            print(f"    {b}-point: {buckets[b]:3d} {'#' * buckets[b]}")

        for dim in ["novelty", "rigor", "impact", "clarity"]:
            vals = [r["score_breakdown"].get(dim, 0) for r in results
                    if isinstance(r["score_breakdown"], dict)]
            if vals:
                print(f"  {dim:10s}: mean={statistics.mean(vals):.1f} stddev={statistics.stdev(vals):.1f}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "cross_model_gpt54_fulltext.json"
    out_path.write_text(json.dumps({"model": "gpt-5.5", "mode": "full_text", "results": results}, ensure_ascii=False, indent=2))
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
