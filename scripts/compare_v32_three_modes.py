"""Compare V3.2 across three modes: abstract-only, truncated fulltext, complete fulltext."""
from __future__ import annotations

import json
import statistics
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
FIXTURES = PROJECT / "tests" / "fixtures"


def load_results(path: Path, nested_key: str | None = None) -> dict[int, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for r in data:
        idx = r.get("idx")
        if idx is None:
            # Old format had no idx, match by arxiv_id → lookup index
            continue
        analysis = r.get(nested_key, r) if nested_key else r
        out[idx] = {
            "arxiv_id": r["arxiv_id"],
            "title": r["title"],
            "hf_likes": r.get("hf_likes", 0),
            "score_total": analysis.get("score_total"),
            "score_breakdown": analysis.get("score_breakdown", {}),
            "weaknesses": analysis.get("weaknesses", []),
            "factual_summary": analysis.get("factual_summary", ""),
            "innovation_points": analysis.get("innovation_points", []),
            "evidence_level": analysis.get("evidence_level", ""),
            "confidence": analysis.get("confidence", 0),
            "tags": analysis.get("tags", []),
            "elapsed_seconds": r.get("elapsed_seconds", 0),
            "prompt_chars": r.get("prompt_chars"),
        }
    return out


def load_old_truncated():
    """Old format: analysis nested, no idx — use arxiv_id to get idx from new index."""
    old = json.loads((FIXTURES / "eval_results_deepseek_v32.json").read_text(encoding="utf-8"))
    new_idx_map = {
        item["arxiv_id"]: item["idx"]
        for item in json.loads((FIXTURES / "eval_paper_fulltext_index.json").read_text(encoding="utf-8"))
    }
    out = {}
    for r in old:
        arxiv_id = r["arxiv_id"]
        idx = new_idx_map.get(arxiv_id)
        if idx is None:
            continue
        a = r["analysis"]
        out[idx] = {
            "arxiv_id": arxiv_id,
            "title": r["title"],
            "hf_likes": r.get("hf_likes", 0),
            "score_total": a["score_total"],
            "score_breakdown": a["score_breakdown"],
            "weaknesses": a.get("weaknesses", []),
            "factual_summary": a.get("factual_summary", ""),
            "innovation_points": a.get("innovation_points", []),
            "evidence_level": a.get("evidence_level", ""),
            "confidence": a.get("confidence", 0),
            "tags": a.get("tags", []),
            "elapsed_seconds": r.get("elapsed_seconds", 0),
        }
    return out


def spearman(x: list[float], y: list[float]) -> float:
    n = len(x)
    if n < 3:
        return 0.0
    def ranks(vals):
        idx = sorted(range(n), key=lambda i: vals[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j < n - 1 and vals[idx[j + 1]] == vals[idx[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[idx[k]] = avg
            i = j + 1
        return r
    rx, ry = ranks(x), ranks(y)
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx = sum((rx[i] - mx) ** 2 for i in range(n))
    dy = sum((ry[i] - my) ** 2 for i in range(n))
    den = (dx * dy) ** 0.5
    return num / den if den else 0.0


def stats(values: list[float]) -> dict:
    return {
        "n": len(values),
        "min": min(values),
        "max": max(values),
        "mean": round(statistics.mean(values), 2),
        "median": statistics.median(values),
        "stdev": round(statistics.stdev(values), 2) if len(values) > 1 else 0,
    }


def main():
    abstract = load_results(FIXTURES / "eval_results_abstract_v32.json")
    truncated = load_old_truncated()
    fulltext = load_results(FIXTURES / "eval_results_fulltext_v32.json")

    common_idx = sorted(set(abstract) & set(truncated) & set(fulltext))
    print(f"Comparable papers: {len(common_idx)}/20\n")

    print("=" * 90)
    print(f"{'V3.2 Three-Mode Comparison':^90}")
    print("=" * 90)

    # Overall score_total stats
    print("\n## Overall score_total (1-40)")
    print(f"{'Mode':<18} {'N':>3} {'min':>5} {'max':>5} {'mean':>6} {'median':>7} {'stdev':>6}")
    for name, d in [("abstract-only", abstract), ("truncated_30K", truncated), ("complete_fulltext", fulltext)]:
        vals = [d[i]["score_total"] for i in common_idx]
        s = stats(vals)
        print(f"{name:<18} {s['n']:>3} {s['min']:>5} {s['max']:>5} {s['mean']:>6} {s['median']:>7} {s['stdev']:>6}")

    # Per-dimension stats
    print("\n## Per-dimension statistics")
    dims = ["novelty", "rigor", "impact", "clarity"]
    for dim in dims:
        print(f"\n### {dim}")
        print(f"{'Mode':<18} {'min':>5} {'max':>5} {'mean':>6} {'stdev':>6}")
        for name, d in [("abstract-only", abstract), ("truncated_30K", truncated), ("complete_fulltext", fulltext)]:
            vals = [d[i]["score_breakdown"][dim] for i in common_idx]
            s = stats(vals)
            print(f"{name:<18} {s['min']:>5} {s['max']:>5} {s['mean']:>6} {s['stdev']:>6}")

    # Pairwise Spearman on score_total
    print("\n## Pairwise Spearman correlation (score_total ranking)")
    modes = [
        ("abstract-only", abstract),
        ("truncated_30K", truncated),
        ("complete_fulltext", fulltext),
    ]
    for i in range(len(modes)):
        for j in range(i + 1, len(modes)):
            na, a = modes[i]
            nb, b = modes[j]
            xa = [a[idx]["score_total"] for idx in common_idx]
            xb = [b[idx]["score_total"] for idx in common_idx]
            rho = spearman(xa, xb)
            print(f"  {na:<18} vs {nb:<18}: ρ = {rho:.3f}")

    # Per-paper delta table (fulltext vs others)
    print("\n## Per-paper score_total: abstract → truncated → fulltext")
    print(f"{'idx':>3} {'arxiv_id':<12} {'hf':>3} {'abs':>4} {'trunc':>6} {'full':>5} {'Δf-a':>5} {'Δf-t':>5}  title")
    for idx in common_idx:
        a = abstract[idx]["score_total"]
        t = truncated[idx]["score_total"]
        f = fulltext[idx]["score_total"]
        hf = abstract[idx]["hf_likes"]
        title = abstract[idx]["title"][:55]
        print(f"{idx:>3} {abstract[idx]['arxiv_id']:<12} {hf:>3} {a:>4} {t:>6} {f:>5} {f-a:>+5} {f-t:>+5}  {title}")

    # Timing
    print("\n## Timing (seconds per paper, avg)")
    for name, d in [("abstract-only", abstract), ("truncated_30K", truncated), ("complete_fulltext", fulltext)]:
        times = [d[i]["elapsed_seconds"] for i in common_idx if d[i].get("elapsed_seconds")]
        if times:
            print(f"  {name:<18} avg={statistics.mean(times):.1f}s  total={sum(times):.0f}s")

    # Weakness count (depth signal)
    print("\n## Weaknesses identified per paper (mean)")
    for name, d in [("abstract-only", abstract), ("truncated_30K", truncated), ("complete_fulltext", fulltext)]:
        counts = [len(d[i].get("weaknesses", [])) for i in common_idx]
        print(f"  {name:<18} mean={statistics.mean(counts):.1f}  range={min(counts)}-{max(counts)}")

    # Confidence
    print("\n## Self-reported confidence (mean)")
    for name, d in [("abstract-only", abstract), ("truncated_30K", truncated), ("complete_fulltext", fulltext)]:
        vals = [d[i].get("confidence", 0) for i in common_idx]
        vals = [v for v in vals if isinstance(v, (int, float))]
        if vals:
            print(f"  {name:<18} mean={statistics.mean(vals):.3f}")

    # Evidence level distribution
    print("\n## Evidence level distribution")
    for name, d in [("abstract-only", abstract), ("truncated_30K", truncated), ("complete_fulltext", fulltext)]:
        from collections import Counter
        c = Counter(d[i].get("evidence_level", "?") for i in common_idx)
        print(f"  {name:<18} {dict(c)}")

    # Save machine-readable summary
    summary = {
        "common_papers": len(common_idx),
        "modes": {
            name: {
                "score_total_stats": stats([d[i]["score_total"] for i in common_idx]),
                "dim_stats": {
                    dim: stats([d[i]["score_breakdown"][dim] for i in common_idx])
                    for dim in dims
                },
                "avg_weaknesses": round(statistics.mean([len(d[i].get("weaknesses", [])) for i in common_idx]), 2),
            }
            for name, d in [("abstract_only", abstract), ("truncated_30K", truncated), ("complete_fulltext", fulltext)]
        },
        "spearman": {
            "abstract_vs_truncated": round(spearman(
                [abstract[i]["score_total"] for i in common_idx],
                [truncated[i]["score_total"] for i in common_idx],
            ), 3),
            "abstract_vs_fulltext": round(spearman(
                [abstract[i]["score_total"] for i in common_idx],
                [fulltext[i]["score_total"] for i in common_idx],
            ), 3),
            "truncated_vs_fulltext": round(spearman(
                [truncated[i]["score_total"] for i in common_idx],
                [fulltext[i]["score_total"] for i in common_idx],
            ), 3),
        },
    }
    out = FIXTURES / "v32_three_modes_comparison.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n\nSummary saved: {out.relative_to(PROJECT)}")


if __name__ == "__main__":
    main()
