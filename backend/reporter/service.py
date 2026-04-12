from __future__ import annotations

import json
import logging
from datetime import date

from backend.core.database import Database
from backend.core.stage_runner import StageRunner
from backend.reporter.cluster import ClusterService
from backend.reporter.report_prompt import build_weekly_report_prompt
from backend.reporter.report_generator import generate_weekly_markdown

logger = logging.getLogger(__name__)


class ReporterService:
    def __init__(
        self,
        db: Database,
        stage_runner: StageRunner,
        llm_client,
        vector_store,
        embedding_collection: str = "paper_embeddings_v1",
        embedding_version_id: int = 1,
    ):
        self._db = db
        self._stage_runner = stage_runner
        self._llm = llm_client
        self._vector_store = vector_store
        self._embedding_collection = embedding_collection
        self._embedding_version_id = embedding_version_id
        self._cluster_service = ClusterService(db)

    async def generate_report(
        self,
        week_start: str,
        week_end: str,
    ) -> int:
        # 1. Get papers analyzed in this window
        papers = await self._db.fetch_all(
            "SELECT p.id, p.title, ar.factual_summary, ar.score_total, ar.tags "
            "FROM paper_analysis pa "
            "JOIN papers p ON pa.paper_id = p.id "
            "JOIN analysis_runs ar ON pa.active_analysis_run_id = ar.id "
            "WHERE pa.active_analyzed_at >= ? AND pa.active_analyzed_at < date(?, '+1 day')",
            (week_start, week_end),
        )
        paper_ids = [p["id"] for p in papers]

        # 2. Get embeddings from vector store
        embeddings_data = self._vector_store.get(
            collection_name=self._embedding_collection,
            ids=paper_ids if paper_ids else ["__nonexistent__"],
            include=["embeddings"],
        )

        valid_ids = embeddings_data.get("ids", [[]])[0]
        valid_embeddings = embeddings_data.get("embeddings", [[]])[0]

        # 3. Run clustering
        cluster_result = await self._cluster_service.run(
            paper_ids=valid_ids,
            embeddings=valid_embeddings,
            embedding_version_id=self._embedding_version_id,
            run_type="stable",
            window_start=week_start,
            window_end=week_end,
        )

        # 4. Build cluster summaries
        cluster_summaries = self._build_cluster_summaries(
            cluster_result, papers, valid_ids,
        )

        # 5. Compute week string
        ws = date.fromisoformat(week_start)
        we = date.fromisoformat(week_end)
        iso_week = ws.isocalendar()
        week_str = f"{iso_week[0]}-W{iso_week[1]:02d}"
        date_range = f"{ws.strftime('%m.%d')} - {we.strftime('%m.%d')}"

        # 6. Call LLM
        messages = build_weekly_report_prompt(
            week_str=week_str,
            date_range=date_range,
            total_papers=len(papers),
            total_analyzed=len(papers),
            cluster_summaries=cluster_summaries,
        )
        llm_report = await self._llm.chat(messages)

        # 7. Build highlights from top-scoring papers
        sorted_papers = sorted(papers, key=lambda p: p["score_total"] or 0, reverse=True)
        highlights = []
        for p in sorted_papers[:5]:
            if (p["score_total"] or 0) >= 8.0:
                highlights.append({
                    "title": p["title"],
                    "reason": (p["factual_summary"] or "")[:60],
                })

        # 8. Generate full markdown
        full_report = generate_weekly_markdown(
            week_str=week_str,
            date_range=date_range,
            cluster_run_id=cluster_result["cluster_run_id"],
            llm_report_body=llm_report,
            highlights=highlights,
        )

        # 9. Store weekly report
        analysis_run_ids = [p["id"] for p in papers]
        report_id = await self._db.execute(
            "INSERT INTO weekly_reports (week_start, week_end, cluster_run_id, "
            "analysis_run_ids_json, report_content, highlights, is_current, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 1, datetime('now'))",
            (
                week_start,
                week_end,
                cluster_result["cluster_run_id"],
                json.dumps(analysis_run_ids),
                full_report,
                json.dumps(highlights),
            ),
        )

        # 10. Create sync stage_run
        await self._stage_runner.create(
            target_type="report",
            target_id=str(report_id),
            stage="sync",
        )

        return report_id

    def _build_cluster_summaries(
        self, cluster_result: dict, papers: list, valid_ids: list[str]
    ) -> list[dict]:
        if not cluster_result.get("labels"):
            return []

        labels = cluster_result["labels"]
        id_to_label = {}
        for pid, label in zip(valid_ids, labels):
            if label >= 0:
                id_to_label[pid] = label

        paper_map = {p["id"]: p for p in papers}
        clusters: dict[int, list[dict]] = {}
        for pid, label in id_to_label.items():
            if pid in paper_map:
                clusters.setdefault(label, []).append(paper_map[pid])

        summaries = []
        for label, cluster_papers in sorted(clusters.items()):
            sorted_cp = sorted(
                cluster_papers, key=lambda p: p["score_total"] or 0, reverse=True
            )
            all_tags = []
            for p in cluster_papers:
                tags_raw = p.get("tags", "[]")
                if isinstance(tags_raw, str):
                    try:
                        all_tags.extend(json.loads(tags_raw))
                    except (json.JSONDecodeError, TypeError):
                        pass
                elif isinstance(tags_raw, list):
                    all_tags.extend(tags_raw)

            top_papers = [
                {
                    "title": p["title"],
                    "score": p["score_total"],
                    "summary": (p["factual_summary"] or "")[:80],
                }
                for p in sorted_cp[:3]
            ]

            common_tags = list(dict.fromkeys(all_tags))[:5]

            summaries.append({
                "cluster_name": f"cluster-{label}",
                "paper_count": len(cluster_papers),
                "top_papers": top_papers,
                "common_tags": common_tags,
            })

        return summaries
