import pytest
from backend.core.database import Database
from backend.core.stage_runner import StageRunner

@pytest.fixture
async def db(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    await db.initialize()
    yield db
    await db.close()

@pytest.fixture
def runner(db):
    return StageRunner(db)

async def _insert_paper(db, paper_id="p1"):
    await db.execute(
        "INSERT INTO papers (id, title, abstract, published_date, first_seen_at, updated_at) "
        "VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))",
        (paper_id, "Test Paper", "Abstract", "2026-04-01"),
    )

async def test_create_stage_run(db, runner):
    await _insert_paper(db)
    run_id = await runner.create(target_type="paper", target_id="p1", stage="pdf_fetch")
    assert run_id > 0
    row = await db.fetch_one("SELECT * FROM stage_runs WHERE id = ?", (run_id,))
    assert row["status"] == "pending"
    assert row["stage"] == "pdf_fetch"

async def test_create_duplicate_is_idempotent(db, runner):
    await _insert_paper(db)
    id1 = await runner.create(target_type="paper", target_id="p1", stage="pdf_fetch")
    id2 = await runner.create(target_type="paper", target_id="p1", stage="pdf_fetch")
    assert id1 == id2

async def test_claim_pending_task(db, runner):
    await _insert_paper(db)
    run_id = await runner.create(target_type="paper", target_id="p1", stage="pdf_fetch")
    claimed = await runner.claim(stage="pdf_fetch", worker_id="worker-1", lease_seconds=300)
    assert claimed is not None
    assert claimed["id"] == run_id
    assert claimed["status"] == "running"
    row = await db.fetch_one("SELECT * FROM stage_runs WHERE id = ?", (run_id,))
    assert row["status"] == "running"
    assert row["worker_id"] == "worker-1"

async def test_claim_returns_none_when_no_pending(db, runner):
    claimed = await runner.claim(stage="pdf_fetch", worker_id="worker-1", lease_seconds=300)
    assert claimed is None

async def test_claim_skips_running_tasks(db, runner):
    await _insert_paper(db)
    await runner.create(target_type="paper", target_id="p1", stage="pdf_fetch")
    await runner.claim(stage="pdf_fetch", worker_id="worker-1", lease_seconds=300)
    claimed2 = await runner.claim(stage="pdf_fetch", worker_id="worker-2", lease_seconds=300)
    assert claimed2 is None

async def test_complete_marks_succeeded(db, runner):
    await _insert_paper(db)
    run_id = await runner.create(target_type="paper", target_id="p1", stage="pdf_fetch")
    await runner.claim(stage="pdf_fetch", worker_id="worker-1", lease_seconds=300)
    await runner.complete(run_id)
    row = await db.fetch_one("SELECT * FROM stage_runs WHERE id = ?", (run_id,))
    assert row["status"] == "succeeded"

async def test_fail_marks_failed_with_error(db, runner):
    await _insert_paper(db)
    run_id = await runner.create(target_type="paper", target_id="p1", stage="pdf_fetch")
    await runner.claim(stage="pdf_fetch", worker_id="worker-1", lease_seconds=300)
    await runner.fail(run_id, error="Connection timeout")
    row = await db.fetch_one("SELECT * FROM stage_runs WHERE id = ?", (run_id,))
    assert row["status"] == "failed"
    assert row["last_error"] == "Connection timeout"

async def test_retry_creates_new_attempt(db, runner):
    await _insert_paper(db)
    run_id = await runner.create(target_type="paper", target_id="p1", stage="pdf_fetch")
    await runner.claim(stage="pdf_fetch", worker_id="worker-1", lease_seconds=300)
    await runner.fail(run_id, error="timeout")
    await runner.retry(run_id)
    row = await db.fetch_one("SELECT * FROM stage_runs WHERE id = ?", (run_id,))
    assert row["status"] == "pending"
    assert row["attempt_no"] == 1
    attempts = await db.fetch_all("SELECT * FROM stage_run_attempts WHERE stage_run_id = ?", (run_id,))
    assert len(attempts) == 1
    assert attempts[0]["status"] == "failed"

async def test_reclaim_expired_lease(db, runner):
    await _insert_paper(db)
    run_id = await runner.create(target_type="paper", target_id="p1", stage="pdf_fetch")
    await runner.claim(stage="pdf_fetch", worker_id="worker-1", lease_seconds=1)
    await db.execute("UPDATE stage_runs SET lease_expires_at = datetime('now', '-10 seconds') WHERE id = ?", (run_id,))
    reclaimed = await runner.reclaim_expired(stage="pdf_fetch", worker_id="worker-2", lease_seconds=300)
    assert reclaimed is not None
    assert reclaimed["worker_id"] == "worker-2"

async def test_claim_is_concurrency_safe(db, runner):
    # 3 pending tasks, 10 concurrent claimers. The SELECT-then-UPDATE race let
    # multiple workers grab the same row -> duplicate stage_run_attempts (UNIQUE
    # violation) / double-claims. Each task must be claimed at most once.
    import asyncio

    for i in range(3):
        await _insert_paper(db, f"p{i}")
        await runner.create(target_type="paper", target_id=f"p{i}", stage="pdf_fetch")

    results = await asyncio.gather(
        *[runner.claim(stage="pdf_fetch", worker_id=f"w{i}", lease_seconds=300) for i in range(10)]
    )

    claimed_ids = [r["id"] for r in results if r is not None]
    assert len(claimed_ids) == 3, f"expected 3 claims, got {len(claimed_ids)}: {claimed_ids}"
    assert len(set(claimed_ids)) == 3, f"a task was double-claimed: {claimed_ids}"

    attempts = await db.fetch_all("SELECT stage_run_id, attempt_no FROM stage_run_attempts")
    keys = [(a["stage_run_id"], a["attempt_no"]) for a in attempts]
    assert len(keys) == len(set(keys)) == 3, f"duplicate attempts: {keys}"


async def test_list_by_status(db, runner):
    await _insert_paper(db, "p1")
    await _insert_paper(db, "p2")
    await runner.create(target_type="paper", target_id="p1", stage="pdf_fetch")
    await runner.create(target_type="paper", target_id="p2", stage="pdf_fetch")
    pending = await runner.list_by_status(stage="pdf_fetch", status="pending")
    assert len(pending) == 2
