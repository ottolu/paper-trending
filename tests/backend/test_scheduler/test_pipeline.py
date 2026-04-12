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
