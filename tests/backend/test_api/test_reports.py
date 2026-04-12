import pytest
from httpx import ASGITransport, AsyncClient

from backend.core.database import Database
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


async def _insert_report(db, week_start="2024-01-15", week_end="2024-01-21"):
    return await db.execute(
        "INSERT INTO weekly_reports (week_start, week_end, report_content, "
        "highlights, is_current, created_at) "
        "VALUES (?, ?, '# Week Report\nContent here.', '[]', 1, datetime('now'))",
        (week_start, week_end),
    )


async def test_list_reports_empty(client):
    resp = await client.get("/api/reports")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


async def test_list_reports_with_data(client, db):
    await _insert_report(db, "2024-01-15", "2024-01-21")
    await _insert_report(db, "2024-01-22", "2024-01-28")

    resp = await client.get("/api/reports")
    data = resp.json()
    assert data["total"] == 2


async def test_get_report_detail(client, db):
    report_id = await _insert_report(db)

    resp = await client.get(f"/api/reports/{report_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["week_start"] == "2024-01-15"
    assert "Content here." in data["report_content"]


async def test_get_report_not_found(client):
    resp = await client.get("/api/reports/999")
    assert resp.status_code == 404
