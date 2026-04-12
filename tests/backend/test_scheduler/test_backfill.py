import pytest

from backend.core.database import Database
from backend.core.stage_runner import StageRunner
from backend.scheduler.backfill import BackfillService


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
def service(db, stage_runner):
    return BackfillService(db=db, stage_runner=stage_runner)


async def test_create_job(service, db):
    job_id = await service.create_job(
        range_start="2024-01-01",
        range_end="2024-01-03",
    )

    assert job_id is not None
    job = await db.fetch_one("SELECT * FROM backfill_jobs WHERE id = ?", (job_id,))
    assert job is not None
    assert job["range_start"] == "2024-01-01"
    assert job["range_end"] == "2024-01-03"
    assert job["status"] == "pending"


async def test_create_job_initializes_days(service, db):
    job_id = await service.create_job(
        range_start="2024-01-01",
        range_end="2024-01-03",
    )

    days = await db.fetch_all(
        "SELECT * FROM backfill_job_days WHERE backfill_job_id = ? ORDER BY work_date",
        (job_id,),
    )
    assert len(days) == 3
    assert days[0]["work_date"] == "2024-01-01"
    assert days[1]["work_date"] == "2024-01-02"
    assert days[2]["work_date"] == "2024-01-03"
    assert all(d["collect_status"] == "pending" for d in days)


async def test_get_job_status(service, db):
    job_id = await service.create_job(
        range_start="2024-01-01",
        range_end="2024-01-02",
    )

    status = await service.get_job_status(job_id)

    assert status is not None
    assert status["job"]["id"] == job_id
    assert len(status["days"]) == 2


async def test_mark_day_stage_completed(service, db):
    job_id = await service.create_job(
        range_start="2024-01-01",
        range_end="2024-01-01",
    )

    await service.mark_day_stage(job_id, "2024-01-01", "collect_status", "succeeded")

    days = await db.fetch_all(
        "SELECT * FROM backfill_job_days WHERE backfill_job_id = ?", (job_id,)
    )
    assert days[0]["collect_status"] == "succeeded"


async def test_get_nonexistent_job(service):
    status = await service.get_job_status(999)
    assert status is None
