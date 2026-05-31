from __future__ import annotations

import ast
import asyncio
import json
import logging
from pathlib import Path

from backend.analyzer.prompts import PROMPT_VERSION, build_analysis_prompt
from backend.core.database import Database
from backend.core.stage_runner import StageRunner

logger = logging.getLogger(__name__)


def score_total_from_breakdown(breakdown: dict | None) -> float:
    """Compute score_total as the mean of the numeric sub-scores.

    The v3 prompt deliberately does NOT emit score_total (see prompts.py); it is
    computed here so the breakdown stays the single source of truth. Matches the
    eval scripts' formula: round(mean(values), 2).
    """
    if not isinstance(breakdown, dict):
        return 0.0
    vals = [v for v in breakdown.values() if isinstance(v, (int, float))]
    return round(sum(vals) / len(vals), 2) if vals else 0.0


class AnalyzerService:
    def __init__(
        self,
        db: Database,
        stage_runner: StageRunner,
        paper_root: str,
        llm_client,
        embedding_client,
        vector_store,
        embedding_version_id: int = 1,
        embedding_collection: str = "paper_embeddings_v1",
    ):
        self._db = db
        self._stage_runner = stage_runner
        self._paper_root = Path(paper_root)
        self._llm = llm_client
        self._embedding = embedding_client
        self._vector_store = vector_store
        self._embedding_version_id = embedding_version_id
        self._embedding_collection = embedding_collection

    async def process_next(self, worker_id: str = "analyzer-1") -> bool:
        task = await self._stage_runner.claim("analyzer", worker_id)
        if not task:
            return False

        try:
            payload_str = task["payload_json"]
            if payload_str:
                try:
                    payload = json.loads(payload_str)
                except (json.JSONDecodeError, TypeError):
                    payload = ast.literal_eval(payload_str)
            else:
                payload = {}

            paper_id = task["target_id"]
            manifest_path = payload.get("chunk_manifest_path", "")
            analysis_basis = payload.get("analysis_basis", "abstract_only")

            manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
            messages = build_analysis_prompt(manifest)
            analysis = await self._llm.chat_json(messages, temperature=0)

            breakdown = analysis.get("score_breakdown", {})
            score_total = score_total_from_breakdown(breakdown)

            analysis_run_id = await self._db.execute(
                "INSERT INTO analysis_runs (paper_id, chunk_manifest_path, chunk_manifest_hash, "
                "input_hash, factual_summary, methodology_inference, innovation_points, "
                "key_takeaways, score_total, score_breakdown, tags, evidence_level, "
                "analysis_basis, evidence_citations, confidence, analysis_model, prompt_version, "
                "status, analyzed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'succeeded', datetime('now'))",
                (
                    paper_id,
                    manifest_path,
                    payload.get("chunk_manifest_hash"),
                    None,
                    analysis.get("factual_summary", ""),
                    analysis.get("methodology_inference", ""),
                    json.dumps(analysis.get("innovation_points", [])),
                    json.dumps(analysis.get("key_takeaways", [])),
                    score_total,
                    json.dumps(breakdown),
                    json.dumps(analysis.get("tags", [])),
                    analysis.get("evidence_level", "limited"),
                    analysis_basis,
                    json.dumps(analysis.get("evidence_citations", [])),
                    analysis.get("confidence", 0),
                    getattr(self._llm, "model", None),
                    PROMPT_VERSION,
                ),
            )

            existing = await self._db.fetch_one(
                "SELECT paper_id FROM paper_analysis WHERE paper_id = ?", (paper_id,)
            )
            if existing:
                await self._db.execute(
                    "UPDATE paper_analysis SET active_analysis_run_id = ?, "
                    "active_analyzed_at = datetime('now') WHERE paper_id = ?",
                    (analysis_run_id, paper_id),
                )
            else:
                await self._db.execute(
                    "INSERT INTO paper_analysis (paper_id, active_analysis_run_id, active_analyzed_at) "
                    "VALUES (?, ?, datetime('now'))",
                    (paper_id, analysis_run_id),
                )

            embed_text = f"{manifest['title']}\n{manifest['abstract']}"
            embeddings = await self._embedding.embed([embed_text])
            if embeddings:
                self._vector_store.get_or_create_collection(self._embedding_collection)
                self._vector_store.upsert(
                    collection_name=self._embedding_collection,
                    ids=[paper_id],
                    embeddings=embeddings,
                    metadatas=[{
                        "paper_id": paper_id,
                        "analysis_basis": analysis_basis,
                        "embedding_version_id": self._embedding_version_id,
                    }],
                )

            await self._stage_runner.complete(task["id"])
            await self._stage_runner.create(
                target_type="paper",
                target_id=paper_id,
                stage="sync",
            )
            return True
        except Exception as e:
            await self._stage_runner.fail(task["id"], str(e))
            return True

    async def process_batch(
        self, max_concurrent: int = 5, max_items: int | None = None,
    ) -> dict:
        sem = asyncio.Semaphore(max_concurrent)

        pending = await self._stage_runner.list_by_status(
            "analyzer", "pending", limit=max_items or 9999,
        )

        async def _process_one():
            async with sem:
                return await self.process_next()

        tasks = [asyncio.create_task(_process_one()) for _ in pending]
        await asyncio.gather(*tasks)

        ok = await self._db.fetch_one(
            "SELECT count(*) as c FROM stage_runs"
            " WHERE stage='analyzer' AND status='succeeded'"
        )
        fail = await self._db.fetch_one(
            "SELECT count(*) as c FROM stage_runs"
            " WHERE stage='analyzer' AND status='failed'"
        )
        return {
            "succeeded": ok["c"],
            "failed": fail["c"],
            "total": len(pending),
        }
