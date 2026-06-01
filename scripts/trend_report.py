"""Cluster the analyzed corpus and synthesize a trend / hot-topic report.

Pipeline:
  1. Load active analysis per paper (score, breakdown, tags, summary) + HF likes + week.
  2. Pull embeddings from ChromaDB, run HDBSCAN (via ClusterService, persisted).
  3. Aggregate per-cluster signals: size, week momentum (W19->W22), academic scores,
     HF likes (kept SEPARATE from academic score per the dual-track rule), top tags/papers.
  4. One LLM synthesis call -> markdown report: hot topics now, predicted emerging
     trends, and academic-vs-community mismatches.

Usage:
    .venv/bin/python -m scripts.trend_report --min-cluster-size 4 --out docs/trend-report-2026-06-01.md
"""
from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import os
import statistics
from collections import Counter
from pathlib import Path

import chromadb
from dotenv import load_dotenv

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
load_dotenv()

from backend.core.database import Database
from backend.core.llm_client import LLMClient

DATA_ROOT = Path("data")
DS_BASE_URL = "https://api.deepseek.com"
LLM_MODEL = "deepseek-v4-pro"
COLLECTION = "paper_embeddings_v1"


def _week(d: str | None) -> str:
    if not d:
        return "?"
    try:
        iso = datetime.date.fromisoformat(d[:10]).isocalendar()
        return f"W{iso[1]:02d}"
    except ValueError:
        return "?"


def _jload(v, default):
    if isinstance(v, (list, dict)):
        return v
    try:
        return json.loads(v) if v else default
    except (json.JSONDecodeError, TypeError):
        return default


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-cluster-size", type=int, default=4)
    ap.add_argument("--min-samples", type=int, default=1)
    ap.add_argument("--selection-method", choices=["eom", "leaf"], default="eom",
                    help="HDBSCAN cluster_selection_method; 'leaf' gives finer topics on big corpora")
    ap.add_argument("--umap-dims", type=int, default=10,
                    help="reduce embeddings to N dims via UMAP(cosine) before HDBSCAN; 0 disables")
    ap.add_argument("--out", type=str, default="docs/trend-report.md")
    ap.add_argument("--preview", action="store_true", help="only print cluster distribution, no LLM")
    args = ap.parse_args()

    db = Database(str(DATA_ROOT / "tracker.db"))
    await db.initialize()
    try:
        rows = await db.fetch_all(
            "SELECT p.id, p.title, p.published_date, "
            "ar.score_total, ar.score_breakdown, ar.tags, ar.factual_summary, ar.innovation_points, "
            "(SELECT hf_likes FROM paper_sources WHERE paper_id=p.id AND source_name='huggingface' "
            " ORDER BY hf_likes DESC LIMIT 1) AS hf_likes "
            "FROM paper_analysis pa "
            "JOIN papers p ON pa.paper_id = p.id "
            "JOIN analysis_runs ar ON pa.active_analysis_run_id = ar.id"
        )
        papers = {}
        for r in rows:
            papers[r["id"]] = {
                "id": r["id"],
                "title": r["title"],
                "week": _week(r["published_date"]),
                "score": r["score_total"] or 0,
                "breakdown": _jload(r["score_breakdown"], {}),
                "tags": _jload(r["tags"], []),
                "summary": (r["factual_summary"] or "")[:200],
                "innovations": _jload(r["innovation_points"], []),
                "likes": r["hf_likes"] or 0,
            }
        print(f"loaded {len(papers)} analyzed papers")
        # Week span for labels. _week() is year-agnostic, so a few papers published
        # in late prior-Dec show as W50-53; drop those stragglers (no 2026 sourcing
        # week exceeds the current week) so the label reflects the real window.
        nums = sorted(int(w[1:]) for w in {p["week"] for p in papers.values()} if w != "?")
        low = [n for n in nums if n <= 45]
        rng = low or nums
        wk_span = f"W{min(rng):02d}-W{max(rng):02d}" if rng else "?"

        # embeddings from ChromaDB (VectorStore.get drops `include`, so go direct)
        col = chromadb.PersistentClient(path=str(DATA_ROOT / "chromadb")).get_collection(COLLECTION)
        ids = list(papers.keys())
        emb = col.get(ids=ids, include=["embeddings"])
        emb_ids = emb["ids"]
        emb_vecs = emb["embeddings"]
        print(f"embeddings: {len(emb_ids)}/{len(ids)} found")

        # cluster in-memory (no DB writes; ClusterService.run needs an embedding_versions FK row)
        import hdbscan as _hdbscan
        import numpy as np
        X = np.array([list(v) for v in emb_vecs])
        # L2-normalize so euclidean distance approximates cosine (text embeddings
        # cluster far better this way -> much less HDBSCAN noise).
        X = X / np.clip(np.linalg.norm(X, axis=1, keepdims=True), 1e-12, None)
        # UMAP dim-reduction before HDBSCAN: raw high-dim embeddings give either a
        # few mega-clusters (eom) or >50% noise (leaf); reducing to ~10 cosine dims
        # yields coherent topics with far less noise (BERTopic-style).
        if args.umap_dims > 0 and len(X) > args.umap_dims:
            try:
                import umap
                X = umap.UMAP(
                    n_components=args.umap_dims, metric="cosine",
                    n_neighbors=15, min_dist=0.0, random_state=42,
                ).fit_transform(X)
                print(f"UMAP -> {X.shape[1]}d")
            except ImportError:
                print("umap not installed; clustering on full-dim embeddings")
        if len(X) >= args.min_cluster_size:
            labels = _hdbscan.HDBSCAN(
                min_cluster_size=args.min_cluster_size, min_samples=args.min_samples,
                cluster_selection_method=args.selection_method,
            ).fit_predict(X).tolist()
        else:
            labels = [-1] * len(X)
        n_clusters = len({lab for lab in labels if lab != -1})
        print(f"HDBSCAN: {n_clusters} clusters, {sum(1 for x in labels if x == -1)} noise")

        # group
        clusters: dict[int, list[dict]] = {}
        for pid, lab in zip(emb_ids, labels):
            clusters.setdefault(int(lab), []).append(papers[pid])

        def cluster_signals(members: list[dict]) -> dict:
            weeks = Counter(m["week"] for m in members)
            tags = Counter(t for m in members for t in m["tags"])
            scores = [m["score"] for m in members]
            likes = [m["likes"] for m in members]
            nov = [m["breakdown"].get("novelty") for m in members if isinstance(m["breakdown"].get("novelty"), (int, float))]
            imp = [m["breakdown"].get("impact") for m in members if isinstance(m["breakdown"].get("impact"), (int, float))]
            return {
                "size": len(members),
                "weeks": {w: weeks.get(w, 0) for w in ["W19", "W20", "W21", "W22"]},
                "avg_score": round(statistics.mean(scores), 2) if scores else 0,
                "avg_novelty": round(statistics.mean(nov), 1) if nov else 0,
                "avg_impact": round(statistics.mean(imp), 1) if imp else 0,
                "likes_median": int(statistics.median(likes)) if likes else 0,
                "likes_max": max(likes) if likes else 0,
                "top_tags": [t for t, _ in tags.most_common(6)],
                "by_score": sorted(members, key=lambda m: -m["score"])[:3],
                "by_likes": sorted(members, key=lambda m: -m["likes"])[:2],
            }

        # build report-input text
        lines = []
        ordered = sorted(
            [(lab, m) for lab, m in clusters.items() if lab != -1],
            key=lambda kv: -len(kv[1]),
        )
        for lab, members in ordered:
            s = cluster_signals(members)
            mom = " ".join(f"{w}:{s['weeks'][w]}" for w in ["W19", "W20", "W21", "W22"])
            lines.append(
                f"\n### cluster-{lab} (n={s['size']})\n"
                f"week momentum: {mom} | avg_score={s['avg_score']} "
                f"(novelty {s['avg_novelty']}, impact {s['avg_impact']}) | "
                f"HF likes median={s['likes_median']} max={s['likes_max']}\n"
                f"tags: {', '.join(s['top_tags'])}\n"
                f"top papers (by score): " + "; ".join(
                    f"[{m['score']}|{m['likes']}↑] {m['title']}" for m in s["by_score"]
                ) + "\n"
                "most upvoted: " + "; ".join(f"[{m['likes']}↑] {m['title']}" for m in s["by_likes"])
            )
        cluster_block = "\n".join(lines)
        # Long-tail (HDBSCAN noise): emerging/singleton topics often hide here, so
        # feed them to the LLM as candidates rather than discarding them.
        noise = sorted(clusters.get(-1, []), key=lambda m: -m["likes"])
        noise_block = "\n".join(
            f"- [{m['score']}|{m['likes']}↑|{m['week']}] {m['title']} "
            f"({', '.join(m['tags'][:3])})" for m in noise
        )
        noise_n = len(noise)
        print(f"{len(ordered)} clusters used, {noise_n} long-tail papers")

        if args.preview:
            print(cluster_block)
            print(f"\n=== long-tail ({noise_n}) ===\n{noise_block}")
            return

        # LLM synthesis
        llm = LLMClient(base_url=DS_BASE_URL, api_key=os.environ["DEEPSEEK_API_KEY"],
                        model=LLM_MODEL, enable_thinking=True)
        sys_prompt = (
            f"你是 AI 研究趋势分析师。下面是 2026 年 ISO 周 {wk_span} 的 HuggingFace 高热论文经过"
            "全文 LLM 分析后的聚类结果。每簇给了规模、周分布（动量）、学术分（novelty/impact，1-10）、"
            "HF 社区点赞（likes，独立信号，勿与学术分混合）、高频标签、代表论文。\n\n"
            "请用中文输出一份趋势报告，包含：\n"
            "1. **主题命名**：给每个 cluster 起一个准确的研究主题名（不要用 cluster-N）。\n"
            "2. **当前热点 topic（排名）**：综合判断当下最热的方向。学术热度（簇规模×avg_score×novelty/impact）"
            "和社区热度（HF likes）**分两栏并列呈现**，不要加权混合；指出二者一致或背离。\n"
            "3. **预判的上升/新兴趋势**：基于周动量（W19→W22 增长）、高 novelty 但目前簇小、以及主题间的"
            "空白地带，推断未来可能成为热点的方向，给出理由。**特别关注「长尾候选」列表**——新兴方向常以单点"
            "形式出现在那里，挑出有潜力的。\n"
            "4. **学术 vs 社区错位案例**：高 likes 低学术分（产品/话题驱动）或高学术分低 likes（被低估）的"
            "具体论文，简述原因。\n"
            "结论要具体、可执行，引用代表论文标题佐证。"
        )
        user_content = (
            f"共 {len(papers)} 篇，{len(ordered)} 个主题簇（另 {noise_n} 篇长尾未归簇）。\n"
            f"{cluster_block}\n\n## 长尾候选（未归簇，按 likes 降序）\n{noise_block}"
        )
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_content},
        ]
        print("calling LLM for synthesis ...", flush=True)
        report = await llm.chat(messages)

        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        header = (
            f"# AI 研究趋势报告 — HF Weekly {wk_span} (2026)\n\n"
            f"> 语料：{len(papers)} 篇全文分析论文 | {len(ordered)} 个主题簇（{noise_n} 篇离群）"
            f" | HDBSCAN(mcs={args.min_cluster_size}, {args.selection_method}) | 模型 {LLM_MODEL}\n\n"
        )
        out.write_text(
            header + report
            + "\n\n---\n## 附：聚类信号原始数据\n" + cluster_block
            + f"\n\n## 附：长尾候选（{noise_n} 篇）\n" + noise_block,
            encoding="utf-8",
        )
        print(f"report written to {out} ({len(report)} chars)")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
