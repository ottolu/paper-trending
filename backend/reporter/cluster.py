from __future__ import annotations

import json
import logging
import uuid

import numpy as np

from backend.core.database import Database

logger = logging.getLogger(__name__)


class ClusterService:
    def __init__(self, db: Database, min_cluster_size: int = 3, min_samples: int = 2):
        self._db = db
        self._min_cluster_size = min_cluster_size
        self._min_samples = min_samples

    async def run(
        self,
        paper_ids: list[str],
        embeddings: list[list[float]],
        embedding_version_id: int,
        run_type: str = "stable",
        window_start: str | None = None,
        window_end: str | None = None,
    ) -> dict:
        cluster_run_id = await self._db.execute(
            "INSERT INTO cluster_runs (run_type, embedding_version_id, window_start, "
            "window_end, paper_count, algorithm_name, algorithm_version, "
            "cluster_params_json, is_stable, created_at) "
            "VALUES (?, ?, ?, ?, ?, 'hdbscan', '0.8', ?, ?, datetime('now'))",
            (
                run_type,
                embedding_version_id,
                window_start,
                window_end,
                len(paper_ids),
                json.dumps({
                    "min_cluster_size": self._min_cluster_size,
                    "min_samples": self._min_samples,
                }),
                run_type == "stable",
            ),
        )

        if not paper_ids or not embeddings:
            return {"cluster_run_id": cluster_run_id, "n_clusters": 0, "labels": []}

        X = np.array(embeddings)
        labels = self._cluster(X)

        unique_labels = set(labels.tolist() if isinstance(labels, np.ndarray) else labels)
        unique_labels.discard(-1)

        entity_map: dict[int, str] = {}
        for label in sorted(unique_labels):
            entity_id = str(uuid.uuid4())
            entity_map[label] = entity_id

            await self._db.execute(
                "INSERT INTO cluster_entities (id, first_seen_run_id, current_name, "
                "status, updated_at) VALUES (?, ?, ?, 'active', datetime('now'))",
                (entity_id, cluster_run_id, f"cluster-{label}"),
            )

            await self._db.execute(
                "INSERT INTO cluster_versions (cluster_entity_id, cluster_run_id, "
                "name, change_type, created_at) "
                "VALUES (?, ?, ?, 'created', datetime('now'))",
                (entity_id, cluster_run_id, f"cluster-{label}"),
            )

        for i, (paper_id, label) in enumerate(zip(paper_ids, labels)):
            label_int = int(label) if isinstance(label, np.integer) else label
            if label_int == -1:
                continue
            entity_id = entity_map[label_int]
            version_row = await self._db.fetch_one(
                "SELECT id FROM cluster_versions WHERE cluster_entity_id = ? "
                "AND cluster_run_id = ?",
                (entity_id, cluster_run_id),
            )
            if version_row:
                await self._db.execute(
                    "INSERT INTO paper_cluster_assignments (paper_id, cluster_run_id, "
                    "cluster_version_id, assignment_type, similarity_score, assigned_at) "
                    "VALUES (?, ?, ?, ?, ?, datetime('now'))",
                    (paper_id, cluster_run_id, version_row["id"], run_type, None),
                )

        return {
            "cluster_run_id": cluster_run_id,
            "n_clusters": len(unique_labels),
            "labels": labels.tolist() if isinstance(labels, np.ndarray) else labels,
        }

    def _cluster(self, X: np.ndarray) -> np.ndarray:
        if len(X) < self._min_cluster_size:
            return np.full(len(X), -1, dtype=int)

        import hdbscan

        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=self._min_cluster_size,
            min_samples=self._min_samples,
        )
        labels = clusterer.fit_predict(X)
        return labels
