from __future__ import annotations
from backend.core.database import Database


class StageRunner:
    def __init__(self, db: Database):
        self._db = db

    async def create(self, target_type: str, target_id: str, stage: str, payload: dict | None = None) -> int:
        logical_job_key = f"{target_type}:{target_id}:{stage}"
        existing = await self._db.fetch_one(
            "SELECT id FROM stage_runs WHERE logical_job_key = ? AND status NOT IN ('cancelled')",
            (logical_job_key,),
        )
        if existing:
            return existing["id"]
        run_id = await self._db.execute(
            "INSERT INTO stage_runs (target_type, target_id, stage, status, logical_job_key, attempt_no, payload_json, created_at, updated_at) "
            "VALUES (?, ?, ?, 'pending', ?, 0, ?, datetime('now'), datetime('now'))",
            (target_type, target_id, stage, logical_job_key, str(payload) if payload else None),
        )
        return run_id

    async def claim(self, stage: str, worker_id: str, lease_seconds: int = 300) -> dict | None:
        row = await self._db.fetch_one(
            "SELECT id FROM stage_runs WHERE stage = ? AND status = 'pending' ORDER BY created_at LIMIT 1",
            (stage,),
        )
        if not row:
            return None
        run_id = row["id"]
        await self._db.execute(
            "UPDATE stage_runs SET status = 'running', worker_id = ?, "
            "lease_expires_at = datetime('now', '+' || ? || ' seconds'), updated_at = datetime('now') "
            "WHERE id = ? AND status = 'pending'",
            (worker_id, str(lease_seconds), run_id),
        )
        current = await self._db.fetch_one("SELECT * FROM stage_runs WHERE id = ?", (run_id,))
        await self._db.execute(
            "INSERT INTO stage_run_attempts (stage_run_id, attempt_no, status, worker_id, lease_expires_at, started_at) "
            "VALUES (?, ?, 'running', ?, ?, datetime('now'))",
            (run_id, current["attempt_no"], worker_id, current["lease_expires_at"]),
        )
        return dict(current)

    async def complete(self, run_id: int) -> None:
        current = await self._db.fetch_one("SELECT attempt_no FROM stage_runs WHERE id = ?", (run_id,))
        await self._db.execute(
            "UPDATE stage_runs SET status = 'succeeded', updated_at = datetime('now') WHERE id = ?",
            (run_id,),
        )
        if current:
            await self._db.execute(
                "UPDATE stage_run_attempts SET status = 'succeeded', finished_at = datetime('now') "
                "WHERE stage_run_id = ? AND attempt_no = ?",
                (run_id, current["attempt_no"]),
            )

    async def fail(self, run_id: int, error: str) -> None:
        current = await self._db.fetch_one("SELECT attempt_no FROM stage_runs WHERE id = ?", (run_id,))
        await self._db.execute(
            "UPDATE stage_runs SET status = 'failed', last_error = ?, last_error_at = datetime('now'), "
            "updated_at = datetime('now') WHERE id = ?",
            (error, run_id),
        )
        if current:
            await self._db.execute(
                "UPDATE stage_run_attempts SET status = 'failed', finished_at = datetime('now'), error_message = ? "
                "WHERE stage_run_id = ? AND attempt_no = ?",
                (error, run_id, current["attempt_no"]),
            )

    async def retry(self, run_id: int) -> None:
        await self._db.execute(
            "UPDATE stage_runs SET status = 'pending', attempt_no = attempt_no + 1, worker_id = NULL, "
            "lease_expires_at = NULL, updated_at = datetime('now') WHERE id = ?",
            (run_id,),
        )

    async def reclaim_expired(self, stage: str, worker_id: str, lease_seconds: int = 300) -> dict | None:
        row = await self._db.fetch_one(
            "SELECT id FROM stage_runs WHERE stage = ? AND status = 'running' AND lease_expires_at < datetime('now') "
            "ORDER BY lease_expires_at LIMIT 1",
            (stage,),
        )
        if not row:
            return None
        run_id = row["id"]
        current = await self._db.fetch_one("SELECT attempt_no FROM stage_runs WHERE id = ?", (run_id,))
        if current:
            await self._db.execute(
                "UPDATE stage_run_attempts SET status = 'failed', finished_at = datetime('now'), "
                "error_message = 'lease expired' WHERE stage_run_id = ? AND attempt_no = ?",
                (run_id, current["attempt_no"]),
            )
        await self._db.execute(
            "UPDATE stage_runs SET status = 'running', worker_id = ?, attempt_no = attempt_no + 1, "
            "lease_expires_at = datetime('now', '+' || ? || ' seconds'), updated_at = datetime('now') WHERE id = ?",
            (worker_id, str(lease_seconds), run_id),
        )
        updated = await self._db.fetch_one("SELECT * FROM stage_runs WHERE id = ?", (run_id,))
        await self._db.execute(
            "INSERT INTO stage_run_attempts (stage_run_id, attempt_no, status, worker_id, lease_expires_at, started_at) "
            "VALUES (?, ?, 'running', ?, ?, datetime('now'))",
            (run_id, updated["attempt_no"], worker_id, updated["lease_expires_at"]),
        )
        return dict(updated)

    async def list_by_status(self, stage: str, status: str, limit: int = 100) -> list[dict]:
        return await self._db.fetch_all(
            "SELECT * FROM stage_runs WHERE stage = ? AND status = ? ORDER BY created_at LIMIT ?",
            (stage, status, limit),
        )
