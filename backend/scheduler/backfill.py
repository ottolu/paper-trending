from __future__ import annotations

import logging
from datetime import date, timedelta

from backend.core.database import Database
from backend.core.stage_runner import StageRunner

logger = logging.getLogger(__name__)


class BackfillService:
    def __init__(self, db: Database, stage_runner: StageRunner):
        self._db = db
        self._stage_runner = stage_runner

    async def create_job(
        self,
        range_start: str,
        range_end: str,
    ) -> int:
        job_id = await self._db.execute(
            "INSERT INTO backfill_jobs (range_start, range_end, status, attempt_no, "
            "updated_at) VALUES (?, ?, 'pending', 0, datetime('now'))",
            (range_start, range_end),
        )

        start = date.fromisoformat(range_start)
        end = date.fromisoformat(range_end)
        current = start
        while current <= end:
            await self._db.execute(
                "INSERT INTO backfill_job_days (backfill_job_id, work_date, "
                "collect_status, pdf_fetch_status, pdf_parse_status, "
                "processor_status, analyzer_status, sync_status, "
                "is_terminal, updated_at) "
                "VALUES (?, ?, 'pending', 'pending', 'pending', "
                "'pending', 'pending', 'pending', 0, datetime('now'))",
                (job_id, current.isoformat()),
            )
            current += timedelta(days=1)

        return job_id

    async def get_job_status(self, job_id: int) -> dict | None:
        job = await self._db.fetch_one(
            "SELECT * FROM backfill_jobs WHERE id = ?", (job_id,)
        )
        if not job:
            return None

        days = await self._db.fetch_all(
            "SELECT * FROM backfill_job_days WHERE backfill_job_id = ? ORDER BY work_date",
            (job_id,),
        )

        return {
            "job": dict(job),
            "days": [dict(d) for d in days],
        }

    async def mark_day_stage(
        self,
        job_id: int,
        work_date: str,
        stage_column: str,
        status: str,
    ) -> None:
        valid_columns = {
            "collect_status",
            "pdf_fetch_status",
            "pdf_parse_status",
            "processor_status",
            "analyzer_status",
            "sync_status",
        }
        if stage_column not in valid_columns:
            raise ValueError(f"Invalid stage column: {stage_column}")

        await self._db.execute(
            f"UPDATE backfill_job_days SET {stage_column} = ?, updated_at = datetime('now') "
            f"WHERE backfill_job_id = ? AND work_date = ?",
            (status, job_id, work_date),
        )
