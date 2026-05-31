import pytest

from backend.config.loader import load_config
from backend.core.database import Database
from backend.core.stage_runner import StageRunner
from backend.scheduler.pipeline import PipelineRunner, STAGE_ORDER
from backend.scheduler.runtime import build_pipeline_runner


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
