# Phase 1: Automation & Orchestration Implementation Plan (Daily ingestion)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Paper Trending self-driving — the FastAPI app, on startup, wires all pipeline services into a `PipelineRunner` and an APScheduler that drains queued work on an interval, ingests the day's top HF papers **daily**, and generates a weekly report on cron — replacing the manual `scripts/` run path.

**Architecture:** Activate the already-implemented-but-dormant orchestration layer. A new `backend/scheduler/runtime.py` builds the stage-service dict + `PipelineRunner` and an `AsyncIOScheduler` with three jobs: interval `pipeline.tick()` (drain), **daily** cron `collect_hf_daily()` (ingest top-N new papers), weekly cron `generate_report()`. `backend/main.py:lifespan` constructs the LLM client + services + scheduler and starts it. Daily ingestion reuses the existing, tested `HuggingFaceFetcher.fetch(target_date)`; the new `CollectorService.collect_hf_daily()` ranks by upvotes, takes top-N, and ingests only papers not already in the DB. A read-only `GET /api/pipeline/status` exposes pending counts.

**Tech Stack:** Python 3.11, FastAPI, APScheduler 3.x (`AsyncIOScheduler`, `CronTrigger`, `IntervalTrigger`), aiosqlite, pytest + pytest-asyncio (`asyncio_mode=auto`).

**Scope notes / constraints:**
- **Daily, not weekly.** Weekly granularity was only for bootstrapping high-quality test content. Production ingests daily (default: yesterday's HF Daily Papers, top 15 by upvotes).
- **Idempotent ingest.** `collect_hf_daily()` skips papers already in the `papers` table, so daily re-runs / multi-day trending papers do NOT re-queue PDF downloads. (`upsert_paper()` unconditionally queues `pdf_fetch`, so we guard at the daily-collect layer; refreshing hf_likes for existing papers is Phase 2.)
- Pipeline `tick()` drains **serially** (single worker). Do NOT parallelize stage workers — `StageRunner.claim()` has a SELECT→UPDATE race that breaks under concurrency (CLAUDE.md). Concurrency is out of scope for Phase 1.
- Trigger/admin endpoints (`POST /pipeline/tick`, `/reports/generate`, etc.) and the frontend are Phase 2/3 — not here.
- The scheduler is gated by env var `PT_SCHEDULER` (default on) so tests/dev can disable auto-start.

---

## File Structure

| File | Create/Modify | Responsibility |
|------|---------------|----------------|
| `pyproject.toml` | Modify | Add `apscheduler>=3.10,<4` dependency |
| `backend/collectors/service.py` | Modify | Add `collect_hf_daily()` (daily top-N new-paper ingest) |
| `backend/scheduler/runtime.py` | Create | `build_pipeline_runner()` + `build_scheduler()` |
| `backend/api/deps.py` | Modify | `set_pipeline_runner()` / `get_pipeline_runner()` |
| `backend/api/pipeline.py` | Create | `GET /api/pipeline/status` |
| `backend/main.py` | Modify | lifespan builds LLM client + services + scheduler; register router; shutdown stops scheduler |
| `tests/backend/test_collectors/test_collect_daily.py` | Create | Tests for `collect_hf_daily` (ranking, top-N, idempotency) |
| `tests/backend/test_scheduler/test_runtime.py` | Create | Tests for `build_pipeline_runner` + `build_scheduler` |
| `tests/backend/test_api/test_pipeline_status.py` | Create | Test for status endpoint |

---

## Task 1: Add APScheduler dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the dependency**

In `pyproject.toml`, under `[project] dependencies = [ ... ]`, add the line:

```toml
    "apscheduler>=3.10,<4",
```

- [ ] **Step 2: Install it**

Run: `.venv/bin/pip install "apscheduler>=3.10,<4"`
Expected: `Successfully installed apscheduler-3.x ...` (+ tzlocal)

- [ ] **Step 3: Verify import**

Run: `.venv/bin/python -c "from apscheduler.schedulers.asyncio import AsyncIOScheduler; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add apscheduler dependency for pipeline scheduling"
```

---

## Task 2: `CollectorService.collect_hf_daily()`

Daily ingest: fetch one day of HF Daily Papers (reusing the existing `HuggingFaceFetcher.fetch`), rank by upvotes, take top-N, and ingest only NEW papers. `upsert_paper()` queues a `pdf_fetch` stage_run per new paper; the scheduler's `tick()` drains downstream.

**Files:**
- Modify: `backend/collectors/service.py`
- Test: `tests/backend/test_collectors/test_collect_daily.py`

- [ ] **Step 1: Write the failing test**

Create `tests/backend/test_collectors/test_collect_daily.py`:

```python
import datetime as _dt

import pytest

from backend.collectors.service import CollectorService
from backend.core.database import Database
from backend.core.stage_runner import StageRunner


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.initialize()
    yield database
    await database.close()


_FAKE_API = [
    {
        "paper": {
            "id": "2401.00001", "title": "A", "summary": "x",
            "authors": [{"name": "Z"}], "publishedAt": "2024-01-15T00:00:00.000Z",
            "upvotes": 99,
        },
        "numComments": 1,
    },
    {
        "paper": {
            "id": "2401.00002", "title": "B", "summary": "y",
            "authors": [], "publishedAt": "2024-01-15T00:00:00.000Z",
            "upvotes": 5,
        },
        "numComments": 0,
    },
]


def _patch_fetch(monkeypatch, svc):
    async def fake_fetch(target_date):
        return svc._hf_fetcher.parse_response(_FAKE_API)
    monkeypatch.setattr(svc._hf_fetcher, "fetch", fake_fetch)


async def test_collect_hf_daily_ingests_top_n_by_upvotes(db, monkeypatch):
    sr = StageRunner(db)
    svc = CollectorService(db, sr)
    _patch_fetch(monkeypatch, svc)

    res = await svc.collect_hf_daily(target_date=_dt.date(2024, 1, 15), top=1)

    assert res["new"] == 1  # only the top-1 by upvotes
    rows = await db.fetch_all("SELECT id FROM papers")
    assert [r["id"] for r in rows] == ["2401.00001"]  # the 99-upvote paper
    pending = await sr.list_by_status("pdf_fetch", "pending")
    assert len(pending) == 1


async def test_collect_hf_daily_skips_existing_no_requeue(db, monkeypatch):
    sr = StageRunner(db)
    svc = CollectorService(db, sr)
    _patch_fetch(monkeypatch, svc)

    first = await svc.collect_hf_daily(target_date=_dt.date(2024, 1, 15), top=15)
    assert first["new"] == 2 and first["skipped"] == 0

    second = await svc.collect_hf_daily(target_date=_dt.date(2024, 1, 15), top=15)
    assert second["new"] == 0 and second["skipped"] == 2

    pending = await sr.list_by_status("pdf_fetch", "pending")
    assert len(pending) == 2  # NOT re-queued on the second run
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/backend/test_collectors/test_collect_daily.py -q`
Expected: FAIL with `AttributeError: 'CollectorService' object has no attribute 'collect_hf_daily'`

- [ ] **Step 3: Write minimal implementation**

In `backend/collectors/service.py`, change the datetime import:

```python
from datetime import date, timedelta
```

Add this module-level constant after `logger = logging.getLogger(__name__)`:

```python
ARXIV_PDF_URL = "https://arxiv.org/pdf/{arxiv_id}"  # no extension -> 200 application/pdf
```

Add this method to `CollectorService` (e.g. right after `collect()`):

```python
    async def collect_hf_daily(
        self,
        target_date: date | None = None,
        top: int = 15,
    ) -> dict:
        """Ingest the top-N NEW papers from one day of HF Daily Papers (by upvotes).

        Each new paper is upserted (which queues a pdf_fetch stage_run). Papers
        already in the DB are skipped, so re-runs / multi-day trending papers do
        not re-queue downloads. Defaults to yesterday (the most recent complete day).
        """
        target_date = target_date or (date.today() - timedelta(days=1))
        raw = await self._hf_fetcher.fetch(target_date=target_date)
        ranked = sorted(raw, key=lambda rp: rp.hf_likes or 0, reverse=True)

        new_count = 0
        skipped = 0
        for rp in ranked[:top]:
            arxiv_id = rp.arxiv_id or rp.source_record_id
            if not arxiv_id:
                continue
            existing = await self._db.fetch_one(
                "SELECT id FROM papers WHERE id = ?", (arxiv_id,)
            )
            if existing:
                skipped += 1
                continue
            lp = LinkedPaper(
                paper_id=arxiv_id,
                title=rp.title,
                authors=rp.authors,
                abstract=rp.abstract or "",
                arxiv_id=arxiv_id,
                arxiv_categories=[],
                published_date=rp.published_date,
                pdf_url=ARXIV_PDF_URL.format(arxiv_id=arxiv_id),
                arxiv_source=None,
                hf_source=rp,
                match_strategy="hf_daily",
                match_confidence=None,
            )
            await self.upsert_paper(lp)
            new_count += 1
        logger.info(
            "HF daily collect %s: %d new, %d skipped (top %d)",
            target_date, new_count, skipped, top,
        )
        return {
            "date": target_date.isoformat(),
            "new": new_count,
            "skipped": skipped,
            "top": top,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/backend/test_collectors/test_collect_daily.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/collectors/service.py tests/backend/test_collectors/test_collect_daily.py
git commit -m "feat: CollectorService.collect_hf_daily (daily top-N new-paper ingest)"
```

---

## Task 3: `build_pipeline_runner()` — wire all stage services

**Files:**
- Create: `backend/scheduler/runtime.py`
- Test: `tests/backend/test_scheduler/test_runtime.py`

- [ ] **Step 1: Write the failing test**

Create `tests/backend/test_scheduler/test_runtime.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/backend/test_scheduler/test_runtime.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.scheduler.runtime'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/scheduler/runtime.py`:

```python
"""Build the live pipeline runner + scheduler from config and shared clients."""
from __future__ import annotations

import logging

from backend.analyzer.service import AnalyzerService
from backend.pdf.fetcher import PdfFetcher
from backend.pdf.parser import PdfParser
from backend.processor.service import ProcessorService
from backend.scheduler.pipeline import PipelineRunner
from backend.sync.service import ObsidianSyncService

logger = logging.getLogger(__name__)


def build_pipeline_runner(
    db, stage_runner, config, llm_client, embedding_client, vector_store
) -> PipelineRunner:
    """Construct every stage service and assemble the PipelineRunner."""
    paper_root = config.storage.paper_root
    services = {
        "pdf_fetch": PdfFetcher(
            db, stage_runner, paper_root=paper_root,
            download_timeout=config.pdf.download_timeout_seconds,
        ),
        "pdf_parse": PdfParser(
            db, stage_runner, paper_root=paper_root,
            parser_name=config.pdf.parser_name, parser_version=config.pdf.parser_version,
        ),
        "processor": ProcessorService(db, stage_runner, paper_root=paper_root),
        "analyzer": AnalyzerService(
            db, stage_runner, paper_root=paper_root,
            llm_client=llm_client, embedding_client=embedding_client,
            vector_store=vector_store,
        ),
        "sync": ObsidianSyncService(
            db, stage_runner, vault_path=config.obsidian.vault_path,
            root_folder=config.obsidian.root_folder,
        ),
    }
    return PipelineRunner(db, stage_runner, services)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/backend/test_scheduler/test_runtime.py -q`
Expected: PASS (2 passed)

> `tests/fixtures/settings_test.yaml` already has `llm/embedding/obsidian/storage/pdf/arxiv/scheduler` blocks. Its `llm.api_key` is `${OPENAI_API_KEY}`, hence the monkeypatch.

- [ ] **Step 5: Commit**

```bash
git add backend/scheduler/runtime.py tests/backend/test_scheduler/test_runtime.py
git commit -m "feat: build_pipeline_runner wires all stage services from config"
```

---

## Task 4: `build_scheduler()` — interval drain + daily collect + weekly report

**Files:**
- Modify: `backend/scheduler/runtime.py`
- Test: `tests/backend/test_scheduler/test_runtime.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/backend/test_scheduler/test_runtime.py`:

```python
from backend.scheduler.runtime import build_scheduler


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
    scheduler.shutdown(wait=False)  # never started; just dispose
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/backend/test_scheduler/test_runtime.py::test_build_scheduler_registers_three_jobs -q`
Expected: FAIL with `ImportError: cannot import name 'build_scheduler'`

- [ ] **Step 3: Write minimal implementation**

Add to the top imports of `backend/scheduler/runtime.py`:

```python
import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
```

Append to `backend/scheduler/runtime.py`:

```python
def _previous_complete_week(today: datetime.date) -> tuple[str, str]:
    """(monday, sunday) ISO dates of the week before `today`'s week."""
    days_since_monday = today.isoweekday() - 1  # Mon=0
    this_monday = today - datetime.timedelta(days=days_since_monday)
    last_monday = this_monday - datetime.timedelta(days=7)
    last_sunday = this_monday - datetime.timedelta(days=1)
    return last_monday.isoformat(), last_sunday.isoformat()


def build_scheduler(
    db, stage_runner, config, pipeline_runner, collector, reporter,
    tick_interval_seconds: int = 30,
) -> AsyncIOScheduler:
    """Assemble (but do not start) the live scheduler with three jobs."""
    scheduler = AsyncIOScheduler()

    async def _tick():
        try:
            n = await pipeline_runner.tick()
            if n:
                logger.info("pipeline tick processed %d items", n)
        except Exception:
            logger.exception("pipeline tick failed")

    async def _collect():
        try:
            res = await collector.collect_hf_daily()  # defaults: yesterday, top 15
            logger.info("scheduled HF daily collect: %s", res)
        except Exception:
            logger.exception("scheduled collect failed")

    async def _report():
        try:
            week_start, week_end = _previous_complete_week(datetime.date.today())
            report_id = await reporter.generate_report(week_start, week_end)
            logger.info("scheduled report %s..%s -> id=%s", week_start, week_end, report_id)
        except Exception:
            logger.exception("scheduled report failed")

    scheduler.add_job(_tick, IntervalTrigger(seconds=tick_interval_seconds), id="pipeline_tick")
    scheduler.add_job(_collect, CronTrigger.from_crontab(config.scheduler.collector_cron), id="collect")
    scheduler.add_job(_report, CronTrigger.from_crontab(config.scheduler.reporter_cron), id="report")
    return scheduler
```

> `config.scheduler.collector_cron` defaults to `"0 2 * * *"` (daily 02:00) — already the right daily cadence for `collect_hf_daily`. `reporter_cron` is `"0 9 * * 1"` (Mondays 09:00).

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/backend/test_scheduler/test_runtime.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/scheduler/runtime.py tests/backend/test_scheduler/test_runtime.py
git commit -m "feat: build_scheduler with interval tick + daily collect + weekly report"
```

---

## Task 5: `pipeline_runner` DI + `GET /api/pipeline/status`

**Files:**
- Modify: `backend/api/deps.py`
- Create: `backend/api/pipeline.py`
- Modify: `backend/main.py` (register router only)
- Test: `tests/backend/test_api/test_pipeline_status.py`

- [ ] **Step 1: Write the failing test**

Create `tests/backend/test_api/test_pipeline_status.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/backend/test_api/test_pipeline_status.py -q`
Expected: FAIL with `AttributeError: module 'backend.api.deps' has no attribute 'set_pipeline_runner'`

- [ ] **Step 3: Write minimal implementation**

In `backend/api/deps.py`, add:

```python
_pipeline_runner = None


def set_pipeline_runner(runner) -> None:
    global _pipeline_runner
    _pipeline_runner = runner


def get_pipeline_runner():
    assert _pipeline_runner is not None, "PipelineRunner not initialized"
    return _pipeline_runner
```

Create `backend/api/pipeline.py`:

```python
from __future__ import annotations

from fastapi import APIRouter

from backend.api.deps import get_pipeline_runner

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.get("/status")
async def pipeline_status() -> dict:
    runner = get_pipeline_runner()
    counts = await runner.get_pending_counts()
    return {"pending": counts, "total_pending": sum(counts.values())}
```

In `backend/main.py`, inside `create_app`, register the router with the others:

```python
    from backend.api.pipeline import router as pipeline_router
    app.include_router(pipeline_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/backend/test_api/test_pipeline_status.py -q`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/api/deps.py backend/api/pipeline.py backend/main.py tests/backend/test_api/test_pipeline_status.py
git commit -m "feat: pipeline_runner DI + GET /api/pipeline/status"
```

---

## Task 6: Start the scheduler in `lifespan`

Build the LLM client + pipeline runner + collector + reporter + scheduler at startup; stop the scheduler at shutdown. Gated by `PT_SCHEDULER` (default on).

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Extend the lifespan body**

In `backend/main.py`, add these imports at the top (with the other backend imports; `os` already exists — do not duplicate):

```python
from backend.api.deps import get_stage_runner, set_pipeline_runner
from backend.collectors.service import CollectorService
from backend.core.llm_client import LLMClient
from backend.reporter.service import ReporterService
from backend.scheduler.runtime import build_pipeline_runner, build_scheduler
```

Inside `lifespan`, after `set_vector_store(vector_store)` and before `yield`, add:

```python
        llm_client = LLMClient(
            base_url=config.llm.base_url,
            api_key=config.llm.api_key,
            model=config.llm.model,
            enable_thinking=config.llm.enable_thinking,
            thinking_budget=config.llm.thinking_budget,
        )
        stage_runner = get_stage_runner()
        pipeline_runner = build_pipeline_runner(
            db, stage_runner, config, llm_client, embedding_client, vector_store
        )
        set_pipeline_runner(pipeline_runner)

        if os.environ.get("PT_SCHEDULER", "on") == "on":
            collector = CollectorService(
                db, stage_runner,
                arxiv_categories=config.arxiv.categories,
                arxiv_interval=config.arxiv.request_interval_seconds,
            )
            reporter = ReporterService(
                db, stage_runner, llm_client=llm_client, vector_store=vector_store
            )
            scheduler = build_scheduler(
                db, stage_runner, config, pipeline_runner, collector, reporter
            )
            scheduler.start()
            app.state.scheduler = scheduler
```

In the shutdown half of `lifespan` (after `yield`), before `await app.state.db.close()`, add:

```python
    if hasattr(app.state, "scheduler"):
        app.state.scheduler.shutdown(wait=False)
```

- [ ] **Step 2: Full suite still passes (lifespan is skipped when `db=` is passed)**

Run: `.venv/bin/pytest tests/ -q`
Expected: all PASS (lifespan does not run under `create_app(db=...)`; no keys/network needed).

- [ ] **Step 3: Manual smoke — scheduler starts, status works, daily collect runs**

Ensure `.env` has `DEEPSEEK_API_KEY` + `SILICONFLOW_API_KEY`, then:

```bash
.venv/bin/uvicorn backend.main:app --port 8000 &
sleep 3
curl -s localhost:8000/api/pipeline/status
# optionally force one daily collect immediately (Python REPL):
.venv/bin/python -c "import asyncio,os; from dotenv import load_dotenv; load_dotenv('.env'); \
from backend.core.database import Database; from backend.core.stage_runner import StageRunner; \
from backend.collectors.service import CollectorService; \
import datetime as d; \
async def go():\n    db=Database('data/tracker.db'); await db.initialize(); \
    svc=CollectorService(db, StageRunner(db)); \
    print(await svc.collect_hf_daily(target_date=d.date.today()-d.timedelta(days=1), top=15)); \
    await db.close()\nasyncio.run(go())"
kill %1
```

Expected: status JSON with pending counts; the collect prints `{"date": ..., "new": N, "skipped": M, "top": 15}`; uvicorn log shows `Scheduler started`. No tracebacks.

- [ ] **Step 4: Verify ruff + full suite**

Run: `.venv/bin/ruff check . && .venv/bin/pytest tests/ -q`
Expected: `All checks passed!` and all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py
git commit -m "feat: start pipeline scheduler in app lifespan (gated by PT_SCHEDULER)"
```

---

## Final Verification & Handoff

- [ ] **Full suite green:** `.venv/bin/pytest tests/ -q`
- [ ] **Lint clean:** `.venv/bin/ruff check .`
- [ ] **Docs:** update `CLAUDE.md` "生产 LLM 接线现状 (drift)" to note it is now wired + scheduled (Phase 1 done, daily ingest); write a short dev-note if any gotcha surfaced (APScheduler/asyncio loop, cron timezone, `claim()` race).

---

## Self-Review (against the gap analysis + the daily-frequency change)

- **Spec coverage:** "no automation" → Tasks 3–6 (runner + scheduler + lifespan). "daily ingest, top 15, idempotent" → Task 2. Observability → Task 5. ✅
- **Daily change applied:** reuses existing tested `HuggingFaceFetcher.fetch(target_date)`; dropped the weekly date-math/urllib module entirely; collect cron uses the existing daily `collector_cron`.
- **Out of scope (intentional):** trigger endpoints, backfill execution, retry generalization, hf_likes refresh-on-existing (Phase 2); frontend (Phase 3); concurrency (blocked by `claim()` race).
- **Type consistency:** `build_pipeline_runner(db, stage_runner, config, llm, emb, vs)` and `build_scheduler(db, stage_runner, config, runner, collector, reporter, tick_interval_seconds=30)` used identically in tests + lifespan. Service constructor kwargs match real signatures read from source. `collect_hf_daily(target_date=None, top=15)`, `generate_report(week_start, week_end)`, `get_pending_counts()` all match `backend/`.
- **Verified fixture:** `tests/fixtures/settings_test.yaml` has all config blocks; `llm.api_key=${OPENAI_API_KEY}` → tests that call `load_config` set it via monkeypatch (Tasks 3 & 4).
