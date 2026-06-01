from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api import deps
from backend.core.database import Database
from backend.core.stage_runner import StageRunner
from backend.main import create_app
from backend.scheduler.pipeline import PipelineRunner


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.initialize()
    yield database
    await database.close()


async def test_pipeline_status_returns_pending_counts(db):
    app = create_app(db=db)
    deps.set_db(db)
    deps.set_pipeline_runner(PipelineRunner(db, StageRunner(db), services={}))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/pipeline/status")

    assert r.status_code == 200
    body = r.json()
    assert body["total_pending"] == 0
    assert set(body["pending"].keys()) == {
        "pdf_fetch", "pdf_parse", "processor", "analyzer", "sync",
    }
