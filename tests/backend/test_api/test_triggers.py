import pytest
from httpx import ASGITransport, AsyncClient

from backend.api import deps
from backend.core.database import Database
from backend.main import create_app


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.initialize()
    yield database
    await database.close()


def _client(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_trigger_tick_runs_in_background(db):
    app = create_app(db=db)
    deps.set_db(db)

    class FakeRunner:
        def __init__(self):
            self.ticked = 0

        async def tick(self):
            self.ticked += 1

        async def get_pending_counts(self):
            return {}

    runner = FakeRunner()
    deps.set_pipeline_runner(runner)

    async with _client(app) as ac:
        r = await ac.post("/api/pipeline/tick")

    assert r.status_code == 202
    assert r.json()["status"] == "accepted"
    assert runner.ticked == 1  # background task executed during request handling


async def test_trigger_collect_passes_params_and_returns_summary(db):
    app = create_app(db=db)
    deps.set_db(db)

    class FakeCollector:
        def __init__(self):
            self.calls = []

        async def collect_hf_daily(self, target_date=None, top=15):
            self.calls.append((target_date, top))
            return {"date": "2024-01-15", "new": 2, "skipped": 0, "top": top}

    collector = FakeCollector()
    deps.set_collector(collector)

    async with _client(app) as ac:
        r = await ac.post("/api/pipeline/collect", json={"target_date": "2024-01-15", "top": 5})

    assert r.status_code == 200
    assert r.json()["new"] == 2
    assert collector.calls[0][1] == 5
    assert collector.calls[0][0].isoformat() == "2024-01-15"


async def test_trigger_collect_rejects_bad_date(db):
    app = create_app(db=db)
    deps.set_db(db)

    class FakeCollector:
        async def collect_hf_daily(self, target_date=None, top=15):
            return {}

    deps.set_collector(FakeCollector())
    async with _client(app) as ac:
        r = await ac.post("/api/pipeline/collect", json={"target_date": "not-a-date"})
    assert r.status_code == 422


async def test_trigger_report_generate(db):
    app = create_app(db=db)
    deps.set_db(db)

    class FakeReporter:
        def __init__(self):
            self.calls = []

        async def generate_report(self, week_start, week_end):
            self.calls.append((week_start, week_end))
            return 7

    reporter = FakeReporter()
    deps.set_reporter(reporter)

    async with _client(app) as ac:
        r = await ac.post(
            "/api/reports/generate",
            json={"week_start": "2026-05-25", "week_end": "2026-05-31"},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["report_id"] == 7
    assert reporter.calls == [("2026-05-25", "2026-05-31")]
