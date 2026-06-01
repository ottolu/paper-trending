# Phase 2: Trigger / Ops Endpoints Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Expose the already-implemented backend capabilities as on-demand HTTP endpoints so a human (and the Phase 3 frontend) can trigger pipeline drain, daily collect, report generation, single-paper re-analysis, and failed-task retry — instead of only waiting for the scheduler.

**Architecture:** Thin FastAPI endpoints wrapping existing services. First expose `CollectorService` + `ReporterService` via the `deps` DI module (they were previously built only inside the scheduler gate). Then add five endpoints to the existing routers. Heavy/long operations (`tick`) run via `BackgroundTasks`; re-analysis reuses `StageRunner.retry()` on the existing analyzer stage_run (so the original chunk manifest is reused).

**Tech Stack:** FastAPI (APIRouter, BackgroundTasks, pydantic models), aiosqlite, pytest + pytest-asyncio (`asyncio_mode=auto`), httpx ASGITransport for API tests.

**Scope / constraints:**
- No auth (consistent with the rest of the app; these are operator endpoints for local/trusted use).
- `/collect`, `/reports/generate`, and a drained `/tick` trigger real DeepSeek/embedding API calls; each response reports what it did.
- Backfill is explicitly OUT (separate phase).
- Endpoints follow existing router conventions (each file's `router` object; `from backend.api.deps import ...`).

---

## File Structure

| File | Create/Modify | Responsibility |
|------|---------------|----------------|
| `backend/api/deps.py` | Modify | `set/get_collector`, `set/get_reporter` |
| `backend/main.py` | Modify | lifespan builds collector+reporter unconditionally, registers them in deps |
| `backend/api/pipeline.py` | Modify | `POST /api/pipeline/tick`, `POST /api/pipeline/collect` |
| `backend/api/reports.py` | Modify | `POST /api/reports/generate` |
| `backend/api/papers.py` | Modify | `POST /api/papers/{paper_id}/analyze` |
| `backend/core/stage_runner.py` | Modify | `retry_failed(stage) -> int` |
| `backend/api/jobs.py` | Modify | `POST /api/stages/retry-failed` |
| `tests/backend/test_main_lifespan.py` | Modify | assert collector/reporter registered after startup |
| `tests/backend/test_api/test_triggers.py` | Create | endpoint tests for tick/collect/generate/analyze/retry-failed |
| `tests/backend/test_stage_runner.py` | Modify | `retry_failed` unit test |

---

## Task 1: Expose collector & reporter via deps (P0)

**Files:** Modify `backend/api/deps.py`, `backend/main.py`; Modify test `tests/backend/test_main_lifespan.py`

- [ ] **Step 1: Write the failing test** — APPEND to `tests/backend/test_main_lifespan.py` a new assertion block. First, add `from backend.api import deps` to the top imports. Then APPEND this test:

```python
def test_lifespan_registers_collector_and_reporter(tmp_path, monkeypatch):
    monkeypatch.setenv("PT_SCHEDULER", "off")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("SILICONFLOW_API_KEY", "sk-test")
    settings = tmp_path / "settings.yaml"
    _write_settings(settings, tmp_path)
    monkeypatch.setenv("SETTINGS_PATH", str(settings))

    from backend.api import deps
    from backend.main import create_app

    app = create_app()
    with TestClient(app):  # runs lifespan startup
        # collector + reporter must be available even with the scheduler OFF
        assert deps.get_collector() is not None
        assert deps.get_reporter() is not None
```

- [ ] **Step 2: Run it, verify FAIL** with `AttributeError: module 'backend.api.deps' has no attribute 'get_collector'`
Run: `.venv/bin/pytest tests/backend/test_main_lifespan.py::test_lifespan_registers_collector_and_reporter -q`

- [ ] **Step 3: Implement.**
(a) In `backend/api/deps.py`, append (follow the existing accessor pattern):
```python
_collector = None
_reporter = None


def set_collector(collector) -> None:
    global _collector
    _collector = collector


def get_collector():
    assert _collector is not None, "CollectorService not initialized"
    return _collector


def set_reporter(reporter) -> None:
    global _reporter
    _reporter = reporter


def get_reporter():
    assert _reporter is not None, "ReporterService not initialized"
    return _reporter
```
(b) In `backend/main.py`: extend the deps import to also import `set_collector, set_reporter`. Then in `lifespan`, MOVE the `CollectorService` and `ReporterService` construction OUT of the `if os.environ.get("PT_SCHEDULER", ...)` block so they are built unconditionally and registered, and have the scheduler block reuse them. The block (replacing the current `if PT_SCHEDULER:` body) becomes:
```python
        collector = CollectorService(
            db, stage_runner,
            arxiv_categories=config.arxiv.categories,
            arxiv_interval=config.arxiv.request_interval_seconds,
        )
        set_collector(collector)
        reporter = ReporterService(
            db, stage_runner, llm_client=llm_client, vector_store=vector_store
        )
        set_reporter(reporter)

        if os.environ.get("PT_SCHEDULER", "on") == "on":
            scheduler = build_scheduler(
                db, stage_runner, config, pipeline_runner, collector, reporter
            )
            scheduler.start()
            app.state.scheduler = scheduler
```

- [ ] **Step 4: Run, verify PASS** (the new test + the existing lifespan tests): `.venv/bin/pytest tests/backend/test_main_lifespan.py -q`

- [ ] **Step 5: ruff + full suite + commit**
```bash
.venv/bin/ruff check backend/api/deps.py backend/main.py tests/backend/test_main_lifespan.py
.venv/bin/pytest tests/ -q
git add backend/api/deps.py backend/main.py tests/backend/test_main_lifespan.py
git commit -m "feat: register collector & reporter in deps (always built, scheduler-independent)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: `POST /api/pipeline/tick` + `POST /api/pipeline/collect`

**Files:** Modify `backend/api/pipeline.py`; Test `tests/backend/test_api/test_triggers.py` (create)

Context: `backend/api/pipeline.py` has `router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])` and a `GET /status`. `PipelineRunner.tick()` is async (drains everything — can be long, so run in background). `CollectorService.collect_hf_daily(target_date: date|None=None, top: int=15)` is async and returns a summary dict.

- [ ] **Step 1: Write the failing test** — create `tests/backend/test_api/test_triggers.py`:

```python
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
        r = await ac.post("/api/pipeline/collect", json={"date": "2024-01-15", "top": 5})

    assert r.status_code == 200
    assert r.json()["new"] == 2
    assert collector.calls[0][1] == 5  # top forwarded
    assert collector.calls[0][0].isoformat() == "2024-01-15"  # date parsed
```

- [ ] **Step 2: Run, verify FAIL** (404 on the new routes): `.venv/bin/pytest tests/backend/test_api/test_triggers.py -q`

- [ ] **Step 3: Implement** — in `backend/api/pipeline.py`, update imports and add the two endpoints:
```python
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from backend.api.deps import get_collector, get_pipeline_runner

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


# ... existing GET /status stays unchanged ...


@router.post("/tick", status_code=202)
async def trigger_tick(background_tasks: BackgroundTasks) -> dict:
    runner = get_pipeline_runner()
    background_tasks.add_task(runner.tick)
    return {"status": "accepted", "note": "draining in background; poll /api/pipeline/status"}


class CollectRequest(BaseModel):
    date: str | None = None
    top: int = 15


@router.post("/collect")
async def trigger_collect(req: CollectRequest) -> dict:
    collector = get_collector()
    target_date = date.fromisoformat(req.date) if req.date else None
    return await collector.collect_hf_daily(target_date=target_date, top=req.top)
```

- [ ] **Step 4: Run, verify PASS** (2 passed): `.venv/bin/pytest tests/backend/test_api/test_triggers.py -q`

- [ ] **Step 5: ruff + full suite + commit**
```bash
.venv/bin/ruff check backend/api/pipeline.py tests/backend/test_api/test_triggers.py
.venv/bin/pytest tests/ -q
git add backend/api/pipeline.py tests/backend/test_api/test_triggers.py
git commit -m "feat: POST /api/pipeline/tick (background drain) + /api/pipeline/collect" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `POST /api/reports/generate`

**Files:** Modify `backend/api/reports.py`; Test: APPEND to `tests/backend/test_api/test_triggers.py`

Context: `backend/api/reports.py` has `router = APIRouter(prefix="/api/reports", tags=["reports"])`. `ReporterService.generate_report(week_start: str, week_end: str)` is async and returns an int (report id). It may take a while (clustering + LLM) — synchronous is acceptable for a deliberate operator action.

- [ ] **Step 1: Write the failing test** — APPEND to `tests/backend/test_api/test_triggers.py`:
```python
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
```

- [ ] **Step 2: Run, verify FAIL** (404): `.venv/bin/pytest tests/backend/test_api/test_triggers.py::test_trigger_report_generate -q`

- [ ] **Step 3: Implement** — in `backend/api/reports.py`, add the import `from pydantic import BaseModel`, `from backend.api.deps import get_reporter` (keep existing `get_db` import), and append:
```python
class GenerateReportRequest(BaseModel):
    week_start: str
    week_end: str


@router.post("/generate")
async def generate_report_endpoint(req: GenerateReportRequest) -> dict:
    reporter = get_reporter()
    try:
        report_id = await reporter.generate_report(req.week_start, req.week_end)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"report_id": report_id, "week_start": req.week_start, "week_end": req.week_end}
```
(`HTTPException` is already imported in `reports.py`.)

- [ ] **Step 4: Run, verify PASS**: `.venv/bin/pytest tests/backend/test_api/test_triggers.py -q`

- [ ] **Step 5: ruff + full suite + commit**
```bash
.venv/bin/ruff check backend/api/reports.py tests/backend/test_api/test_triggers.py
.venv/bin/pytest tests/ -q
git add backend/api/reports.py tests/backend/test_api/test_triggers.py
git commit -m "feat: POST /api/reports/generate" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `POST /api/papers/{paper_id}/analyze`

**Files:** Modify `backend/api/papers.py`; Test: APPEND to `tests/backend/test_api/test_triggers.py`

Context: `backend/api/papers.py` has `router = APIRouter(prefix="/api/papers", tags=["papers"])`, imports `get_db` and `HTTPException`. Re-analysis must reuse the existing analyzer stage_run (its payload points at the chunk manifest) via `StageRunner.retry()`, because `StageRunner.create()` is idempotent on `logical_job_key` and would NOT re-queue. Analyzer stage_runs have `target_id = <paper_id>` and `stage = 'analyzer'`.

- [ ] **Step 1: Write the failing test** — APPEND to `tests/backend/test_api/test_triggers.py`:
```python
from backend.core.stage_runner import StageRunner


async def _insert_paper(db, paper_id):
    await db.execute(
        "INSERT INTO papers (id, title, first_seen_at, updated_at) "
        "VALUES (?, ?, datetime('now'), datetime('now'))",
        (paper_id, "T"),
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
    await sr.complete(run_id)  # mark succeeded so we prove it gets reset to pending

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
```
> If `papers.id` or `stage_runs.target_id` has NOT-NULL columns beyond what's inserted above, adjust `_insert_paper` to satisfy them (read `backend/core/schema.sql`). The `db` fixture and `deps`/`_client` helpers come from earlier in this same test file.

- [ ] **Step 2: Run, verify FAIL** (404 on the route itself, or AttributeError): `.venv/bin/pytest tests/backend/test_api/test_triggers.py -q`

- [ ] **Step 3: Implement** — in `backend/api/papers.py`, add `from backend.api.deps import get_db, get_stage_runner` (extend the existing import) and append:
```python
@router.post("/{paper_id}/analyze")
async def reanalyze_paper(paper_id: str) -> dict:
    db = get_db()
    stage_runner = get_stage_runner()
    row = await db.fetch_one(
        "SELECT id FROM stage_runs WHERE target_id = ? AND stage = 'analyzer' "
        "ORDER BY id DESC LIMIT 1",
        (paper_id,),
    )
    if not row:
        raise HTTPException(
            status_code=404,
            detail="No analyzer task for this paper; run the pipeline first",
        )
    await stage_runner.retry(row["id"])
    return {"status": "requeued", "paper_id": paper_id, "stage_run_id": row["id"]}
```

- [ ] **Step 4: Run, verify PASS**: `.venv/bin/pytest tests/backend/test_api/test_triggers.py -q`

- [ ] **Step 5: ruff + full suite + commit**
```bash
.venv/bin/ruff check backend/api/papers.py tests/backend/test_api/test_triggers.py
.venv/bin/pytest tests/ -q
git add backend/api/papers.py tests/backend/test_api/test_triggers.py
git commit -m "feat: POST /api/papers/{id}/analyze (re-queue analysis via retry)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: `StageRunner.retry_failed()` + `POST /api/stages/retry-failed`

**Files:** Modify `backend/core/stage_runner.py`, `backend/api/jobs.py`; Test: modify `tests/backend/test_stage_runner.py` + APPEND to `tests/backend/test_api/test_triggers.py`

Context: `backend/core/stage_runner.py` already has `retry(run_id)` (sets status pending, attempt_no+1). `backend/api/jobs.py` has `router = APIRouter(tags=["jobs"])` (NO prefix; absolute paths) with `POST /api/stages/retry` using a `RetryRequest` pydantic model and `get_stage_runner`.

- [ ] **Step 1: Write the failing unit test** — APPEND to `tests/backend/test_stage_runner.py` (it already has a `db` fixture; reuse it; match the file's existing imports/style):
```python
async def test_retry_failed_resets_all_failed_in_stage(db):
    from backend.core.stage_runner import StageRunner

    sr = StageRunner(db)
    ids = []
    for i in range(3):
        rid = await sr.create(target_type="paper", target_id=f"p{i}", stage="analyzer")
        await sr.fail(rid, "boom")
        ids.append(rid)
    # a pending one in the same stage must be left alone
    other = await sr.create(target_type="paper", target_id="p-ok", stage="analyzer")

    n = await sr.retry_failed("analyzer")

    assert n == 3
    for rid in ids:
        row = await db.fetch_one("SELECT status FROM stage_runs WHERE id = ?", (rid,))
        assert row["status"] == "pending"
    row = await db.fetch_one("SELECT status FROM stage_runs WHERE id = ?", (other,))
    assert row["status"] == "pending"  # was already pending, unchanged
```
> If `stage_runs.target_id` has a foreign key to `papers.id`, insert the papers first (check `backend/core/schema.sql`; model on existing `test_stage_runner.py` patterns).

- [ ] **Step 2: Run, verify FAIL** with `AttributeError: 'StageRunner' object has no attribute 'retry_failed'`
Run: `.venv/bin/pytest tests/backend/test_stage_runner.py::test_retry_failed_resets_all_failed_in_stage -q`

- [ ] **Step 3: Implement** — in `backend/core/stage_runner.py`, add the method (e.g. right after `retry`):
```python
    async def retry_failed(self, stage: str) -> int:
        rows = await self._db.fetch_all(
            "SELECT id FROM stage_runs WHERE stage = ? AND status = 'failed'",
            (stage,),
        )
        for row in rows:
            await self.retry(row["id"])
        return len(rows)
```

- [ ] **Step 4: Run the unit test, verify PASS**: `.venv/bin/pytest tests/backend/test_stage_runner.py::test_retry_failed_resets_all_failed_in_stage -q`

- [ ] **Step 5: Add the endpoint test** — APPEND to `tests/backend/test_api/test_triggers.py`:
```python
async def test_retry_failed_endpoint(db):
    app = create_app(db=db)
    deps.set_db(db)
    sr = StageRunner(db)
    for i in range(2):
        rid = await sr.create(target_type="paper", target_id=f"f{i}", stage="pdf_fetch")
        await sr.fail(rid, "boom")

    async with _client(app) as ac:
        r = await ac.post("/api/stages/retry-failed", json={"stage": "pdf_fetch"})

    assert r.status_code == 200
    assert r.json()["reset"] == 2
    pend = await sr.list_by_status("pdf_fetch", "pending")
    assert len(pend) == 2
```

- [ ] **Step 6: Implement the endpoint** — in `backend/api/jobs.py`, append:
```python
class RetryFailedRequest(BaseModel):
    stage: str


@router.post("/api/stages/retry-failed")
async def retry_failed_stage(req: RetryFailedRequest):
    stage_runner = get_stage_runner()
    count = await stage_runner.retry_failed(req.stage)
    return {"status": "accepted", "stage": req.stage, "reset": count}
```
(`BaseModel`, `APIRouter`, `get_stage_runner` are already imported in `jobs.py`.)

- [ ] **Step 7: Run, verify PASS** (both new tests): `.venv/bin/pytest tests/backend/test_api/test_triggers.py tests/backend/test_stage_runner.py -q`

- [ ] **Step 8: ruff + full suite + commit**
```bash
.venv/bin/ruff check backend/core/stage_runner.py backend/api/jobs.py tests/backend/test_api/test_triggers.py tests/backend/test_stage_runner.py
.venv/bin/pytest tests/ -q
git add backend/core/stage_runner.py backend/api/jobs.py tests/backend/test_api/test_triggers.py tests/backend/test_stage_runner.py
git commit -m "feat: StageRunner.retry_failed + POST /api/stages/retry-failed" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Final Verification & Handoff
- [ ] `.venv/bin/pytest tests/ -q` → all pass
- [ ] `.venv/bin/ruff check .` → feature files clean
- [ ] Live smoke (optional): `PT_SCHEDULER=off uvicorn backend.main:app` then `curl -XPOST localhost:8000/api/pipeline/collect -d '{"top":5}' -H 'content-type: application/json'` (fetches HF + queues pdf_fetch; no LLM), and `curl localhost:8000/api/pipeline/status`.
- [ ] Update `CLAUDE.md` API Layer section to list the new endpoints. Write a dev-note only if a gotcha surfaced.

## Self-Review
- **Coverage:** P0 → Task 1; tick/collect → Task 2; reports/generate → Task 3; papers/{id}/analyze → Task 4; retry-failed → Task 5. ✅
- **Out of scope (intentional):** backfill execution; auth; making `/reports/generate` async.
- **Type/contract consistency:** endpoints call the real signatures verified from source — `collect_hf_daily(target_date=None, top=15)`, `generate_report(week_start, week_end)`, `tick()`, `retry(run_id)`, new `retry_failed(stage)`. DI accessors `get_collector`/`get_reporter` added in Task 1 and used in Tasks 2–3.
- **Idempotency note:** `/papers/{id}/analyze` uses `retry()` (not `create()`) precisely because `create()` is idempotent on `logical_job_key` and would not re-queue an existing run.
