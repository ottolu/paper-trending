from __future__ import annotations

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


async def test_get_pending_counts_above_100(db):
    """get_pending_counts must report the true count even when >100 items are pending.

    The old implementation used len(list_by_status(...)) which caps at the default
    limit=100, so 101 pending items would be reported as 100.
    """
    sr = StageRunner(db)
    runner = PipelineRunner(db, sr, services={})

    # stage_runs.target_id has no FK to papers, so we can insert directly
    for i in range(101):
        await sr.create(target_type="paper", target_id=f"p{i}", stage="pdf_fetch")

    counts = await runner.get_pending_counts()
    assert counts["pdf_fetch"] == 101, (
        f"expected 101 but got {counts['pdf_fetch']} — "
        "likely capped at list_by_status default limit=100"
    )
