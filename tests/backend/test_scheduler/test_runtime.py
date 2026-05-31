from datetime import date, timedelta

import pytest

from backend.config.loader import load_config
from backend.core.database import Database
from backend.core.stage_runner import StageRunner
from backend.scheduler.pipeline import PipelineRunner, STAGE_ORDER
from backend.scheduler.runtime import _previous_complete_week, build_pipeline_runner, build_scheduler


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.initialize()
    yield database
    await database.close()


class _Fake:  # stand-in for llm / embedding / vector store
    pass


async def test_build_pipeline_runner_has_all_stages(db, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")  # settings_test.yaml resolves ${OPENAI_API_KEY}
    config = load_config("tests/fixtures/settings_test.yaml")
    sr = StageRunner(db)
    runner = build_pipeline_runner(db, sr, config, _Fake(), _Fake(), _Fake())
    assert set(runner._services.keys()) == set(STAGE_ORDER)


async def test_tick_drains_a_queued_stage_via_fake_service(db):
    sr = StageRunner(db)
    calls = {"n": 0}

    class OneShotService:
        async def process_next(self, worker_id="w"):
            if calls["n"] >= 1:
                return False
            calls["n"] += 1
            return True

    runner = PipelineRunner(db, sr, services={"pdf_fetch": OneShotService()})
    assert await runner.tick() == 1


async def test_build_scheduler_registers_three_jobs(db, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    config = load_config("tests/fixtures/settings_test.yaml")
    sr = StageRunner(db)
    runner = build_pipeline_runner(db, sr, config, _Fake(), _Fake(), _Fake())

    class _Collector:
        async def collect_hf_daily(self):
            return {}

    class _Reporter:
        async def generate_report(self, a, b):
            return 0

    scheduler = build_scheduler(
        db, sr, config, runner, _Collector(), _Reporter(), tick_interval_seconds=30
    )
    assert {j.id for j in scheduler.get_jobs()} == {"pipeline_tick", "collect", "report"}
    if scheduler.running:
        scheduler.shutdown(wait=False)  # never started; just dispose


@pytest.mark.parametrize(
    "today",
    [date(2026, 6, 1), date(2026, 6, 4), date(2026, 6, 7)],  # three different weekdays
)
def test_previous_complete_week_returns_prior_monday_to_sunday(today):
    start, end = _previous_complete_week(today)
    s = date.fromisoformat(start)
    e = date.fromisoformat(end)
    assert s.isoweekday() == 1          # Monday
    assert e.isoweekday() == 7          # Sunday
    assert (e - s).days == 6            # a full Mon..Sun week
    this_monday = today - timedelta(days=today.isoweekday() - 1)
    assert e == this_monday - timedelta(days=1)   # ended the day before this week's Monday
    assert s == this_monday - timedelta(days=7)   # the Monday one week earlier
