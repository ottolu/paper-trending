import pytest
from httpx import ASGITransport, AsyncClient

from backend.core.database import Database
from backend.core.stage_runner import StageRunner
from backend.main import create_app


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
async def client(db):
    app = create_app(db=db)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_retry_stage(client, db):
    runner = StageRunner(db)
    run_id = await runner.create("paper", "paper-001", "analyzer")
    task = await runner.claim("analyzer", "worker-1")
    await runner.fail(task["id"], "some error")

    resp = await client.post("/api/stages/retry", json={
        "stage_run_id": run_id,
        "reason": "manual_retry",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "accepted"

    row = await db.fetch_one("SELECT * FROM stage_runs WHERE id = ?", (run_id,))
    assert row["status"] == "pending"
