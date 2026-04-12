# Scheduler + Backfiller (Plan 9) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Scheduler that orchestrates the daily pipeline (collect → pdf_fetch → pdf_parse → processor → analyzer → sync) and the Backfiller that manages historical date-range backfill jobs, tracking per-day progress via `backfill_jobs` and `backfill_job_days`.

**Architecture:** `PipelineRunner` processes pending stage_runs across all stages in priority order. `BackfillService` creates backfill_jobs, initializes per-day records, and triggers collection per day. Both share the existing stage idempotency rules via StageRunner.

**Tech Stack:** existing Database, StageRunner, CollectorService from Plans 1-2.

---

## File Structure

| File | Responsibility |
|------|---------------|
| `backend/scheduler/__init__.py` | Package init |
| `backend/scheduler/pipeline.py` | `PipelineRunner` — process pending stages in order |
| `backend/scheduler/backfill.py` | `BackfillService` — create/manage backfill jobs |
| `tests/backend/test_scheduler/__init__.py` | Test package init |
| `tests/backend/test_scheduler/test_pipeline.py` | Tests for PipelineRunner |
| `tests/backend/test_scheduler/test_backfill.py` | Tests for BackfillService |

---

### Task 1: PipelineRunner

**Files:**
- Create: `backend/scheduler/__init__.py`
- Create: `backend/scheduler/pipeline.py`
- Create: `tests/backend/test_scheduler/__init__.py`
- Create: `tests/backend/test_scheduler/test_pipeline.py`

- [ ] **Step 1: Write the failing tests**

```python
from unittest.mock import AsyncMock

import pytest

from backend.core.database import Database
from backend.core.stage_runner import StageRunner
from backend.scheduler.pipeline import PipelineRunner


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
def stage_runner(db):
    return StageRunner(db)


@pytest.fixture
def mock_services():
    return {
        "pdf_fetch": AsyncMock(process_next=AsyncMock(return_value=False)),
        "pdf_parse": AsyncMock(process_next=AsyncMock(return_value=False)),
        "processor": AsyncMock(process_next=AsyncMock(return_value=False)),
        "analyzer": AsyncMock(process_next=AsyncMock(return_value=False)),
        "sync": AsyncMock(process_next=AsyncMock(return_value=False)),
    }


@pytest.fixture
def runner(db, stage_runner, mock_services):
    return PipelineRunner(db=db, stage_runner=stage_runner, services=mock_services)


async def test_tick_processes_pending_stages(runner, stage_runner, mock_services):
    await stage_runner.create("paper", "paper-001", "pdf_fetch")

    mock_services["pdf_fetch"].process_next = AsyncMock(
        side_effect=[True, False]
    )

    processed = await runner.tick()

    assert processed >= 1
    mock_services["pdf_fetch"].process_next.assert_called()


async def test_tick_returns_zero_when_nothing_pending(runner):
    processed = await runner.tick()
    assert processed == 0


async def test_tick_processes_multiple_stages(runner, stage_runner, mock_services):
    await stage_runner.create("paper", "p1", "pdf_fetch")
    await stage_runner.create("paper", "p2", "analyzer")

    mock_services["pdf_fetch"].process_next = AsyncMock(
        side_effect=[True, False]
    )
    mock_services["analyzer"].process_next = AsyncMock(
        side_effect=[True, False]
    )

    processed = await runner.tick()

    assert processed >= 2


async def test_get_pending_counts(runner, stage_runner):
    await stage_runner.create("paper", "p1", "pdf_fetch")
    await stage_runner.create("paper", "p2", "pdf_fetch")
    await stage_runner.create("paper", "p3", "analyzer")

    counts = await runner.get_pending_counts()

    assert counts["pdf_fetch"] == 2
    assert counts["analyzer"] == 1
    assert counts["processor"] == 0
```

- [ ] **Step 2: Write the implementation**

```python
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
            rows = await self._stage_runner.list_by_status(stage, "pending")
            counts[stage] = len(rows)
        return counts
```

- [ ] **Step 3: Run tests, lint, commit**

```bash
pytest tests/backend/test_scheduler/test_pipeline.py -v
ruff check backend/scheduler/ tests/backend/test_scheduler/
git commit -m "feat: pipeline runner for orchestrating stage processing"
```

---

### Task 2: BackfillService

**Files:**
- Create: `backend/scheduler/backfill.py`
- Create: `tests/backend/test_scheduler/test_backfill.py`

- [ ] **Step 1: Write the failing tests**

```python
from datetime import date

import pytest

from backend.core.database import Database
from backend.core.stage_runner import StageRunner
from backend.scheduler.backfill import BackfillService


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
def stage_runner(db):
    return StageRunner(db)


@pytest.fixture
def service(db, stage_runner):
    return BackfillService(db=db, stage_runner=stage_runner)


async def test_create_job(service, db):
    job_id = await service.create_job(
        range_start="2024-01-01",
        range_end="2024-01-03",
    )

    assert job_id is not None
    job = await db.fetch_one("SELECT * FROM backfill_jobs WHERE id = ?", (job_id,))
    assert job is not None
    assert job["range_start"] == "2024-01-01"
    assert job["range_end"] == "2024-01-03"
    assert job["status"] == "pending"


async def test_create_job_initializes_days(service, db):
    job_id = await service.create_job(
        range_start="2024-01-01",
        range_end="2024-01-03",
    )

    days = await db.fetch_all(
        "SELECT * FROM backfill_job_days WHERE backfill_job_id = ? ORDER BY work_date",
        (job_id,),
    )
    assert len(days) == 3
    assert days[0]["work_date"] == "2024-01-01"
    assert days[1]["work_date"] == "2024-01-02"
    assert days[2]["work_date"] == "2024-01-03"
    assert all(d["collect_status"] == "pending" for d in days)


async def test_get_job_status(service, db):
    job_id = await service.create_job(
        range_start="2024-01-01",
        range_end="2024-01-02",
    )

    status = await service.get_job_status(job_id)

    assert status is not None
    assert status["job"]["id"] == job_id
    assert len(status["days"]) == 2


async def test_mark_day_stage_completed(service, db):
    job_id = await service.create_job(
        range_start="2024-01-01",
        range_end="2024-01-01",
    )

    await service.mark_day_stage(job_id, "2024-01-01", "collect_status", "succeeded")

    days = await db.fetch_all(
        "SELECT * FROM backfill_job_days WHERE backfill_job_id = ?", (job_id,)
    )
    assert days[0]["collect_status"] == "succeeded"


async def test_get_nonexistent_job(service):
    status = await service.get_job_status(999)
    assert status is None
```

- [ ] **Step 2: Write the implementation**

```python
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
            "collect_status", "pdf_fetch_status", "pdf_parse_status",
            "processor_status", "analyzer_status", "sync_status",
        }
        if stage_column not in valid_columns:
            raise ValueError(f"Invalid stage column: {stage_column}")

        await self._db.execute(
            f"UPDATE backfill_job_days SET {stage_column} = ?, updated_at = datetime('now') "
            f"WHERE backfill_job_id = ? AND work_date = ?",
            (status, job_id, work_date),
        )
```

- [ ] **Step 3: Run tests, lint, commit**

```bash
pytest tests/backend/test_scheduler/test_backfill.py -v
ruff check backend/scheduler/ tests/backend/test_scheduler/
git commit -m "feat: backfill service for historical date-range data collection"
```

---

### Task 3: Full Test Suite Verification

- [ ] **Step 1: Run all tests**

Run: `pytest tests/ -v`
Expected: All pass (~162 total)

- [ ] **Step 2: Run linter**

Run: `ruff check .`
Expected: All checks passed
