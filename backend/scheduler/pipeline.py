from __future__ import annotations

import logging

from backend.core.database import Database
from backend.core.stage_runner import StageRunner

logger = logging.getLogger(__name__)

STAGE_ORDER = ["pdf_fetch", "pdf_parse", "processor", "analyzer", "sync"]


class PipelineRunner:
    def __init__(
        self,
        db: Database,
        stage_runner: StageRunner,
        services: dict,
    ):
        self._db = db
        self._stage_runner = stage_runner
        self._services = services

    async def tick(self) -> int:
        total_processed = 0
        for stage in STAGE_ORDER:
            service = self._services.get(stage)
            if not service:
                continue
            while True:
                result = await service.process_next()
                if not result:
                    break
                total_processed += 1
        return total_processed

    async def get_pending_counts(self) -> dict[str, int]:
        counts = {}
        for stage in STAGE_ORDER:
            row = await self._db.fetch_one(
                "SELECT COUNT(*) AS c FROM stage_runs WHERE stage = ? AND status = 'pending'",
                (stage,),
            )
            counts[stage] = row["c"] if row else 0
        return counts
