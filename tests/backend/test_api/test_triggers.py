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


async def test_trigger_report_generate_rejects_bad_date(db):
    app = create_app(db=db)
    deps.set_db(db)

    class FakeReporter:
        async def generate_report(self, week_start, week_end):
            return 1

    deps.set_reporter(FakeReporter())
    async with _client(app) as ac:
        r = await ac.post(
            "/api/reports/generate",
            json={"week_start": "nope", "week_end": "2026-05-31"},
        )
    assert r.status_code == 422


from backend.core.stage_runner import StageRunner  # noqa: E402


async def _insert_paper(db, paper_id):
    await db.execute(
        "INSERT INTO papers (id, title, abstract, first_seen_at, updated_at) "
        "VALUES (?, ?, ?, datetime('now'), datetime('now'))",
        (paper_id, "T", ""),
    )


async def test_reanalyze_paper_requeues_existing_analyzer_run(db):
    app = create_app(db=db)
    deps.set_db(db)
    sr = StageRunner(db)
    await _insert_paper(db, "2401.55555")
    run_id = await sr.create(
        target_type="paper", target_id="2401.55555", stage="analyzer",
        payload={"chunk_manifest_path": "/tmp/m.json"},
    )
    await sr.complete(run_id)  # mark succeeded; prove it gets reset to pending

    async with _client(app) as ac:
        r = await ac.post("/api/papers/2401.55555/analyze")

    assert r.status_code == 200
    assert r.json()["status"] == "requeued"
    row = await db.fetch_one("SELECT status FROM stage_runs WHERE id = ?", (run_id,))
    assert row["status"] == "pending"


async def test_reanalyze_unknown_paper_404(db):
    app = create_app(db=db)
    deps.set_db(db)
    async with _client(app) as ac:
        r = await ac.post("/api/papers/does-not-exist/analyze")
    assert r.status_code == 404
