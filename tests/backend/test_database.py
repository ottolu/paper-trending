import pytest

from backend.core.database import Database


@pytest.fixture
async def db(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    await db.initialize()
    yield db
    await db.close()


async def test_initialize_creates_tables(db):
    tables = await db.fetch_all(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    table_names = {row["name"] for row in tables}
    expected = {
        "papers",
        "paper_sources",
        "paper_files",
        "pdf_extractions",
        "stage_runs",
        "stage_run_attempts",
        "analysis_runs",
        "paper_analysis",
        "embedding_versions",
        "cluster_runs",
        "cluster_entities",
        "cluster_versions",
        "paper_cluster_assignments",
        "weekly_reports",
        "sync_log",
        "backfill_jobs",
        "backfill_job_days",
    }
    assert expected.issubset(table_names)


async def test_execute_and_fetch_one(db):
    await db.execute(
        "INSERT INTO papers (id, title, abstract, published_date, first_seen_at, updated_at) "
        "VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))",
        ("2026.12345", "Test Paper", "An abstract", "2026-04-01"),
    )
    row = await db.fetch_one("SELECT * FROM papers WHERE id = ?", ("2026.12345",))
    assert row["title"] == "Test Paper"
    assert row["id"] == "2026.12345"


async def test_fetch_all_returns_list(db):
    await db.execute(
        "INSERT INTO papers (id, title, abstract, published_date, first_seen_at, updated_at) "
        "VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))",
        ("p1", "Paper 1", "Abstract 1", "2026-04-01"),
    )
    await db.execute(
        "INSERT INTO papers (id, title, abstract, published_date, first_seen_at, updated_at) "
        "VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))",
        ("p2", "Paper 2", "Abstract 2", "2026-04-02"),
    )
    rows = await db.fetch_all("SELECT * FROM papers ORDER BY id")
    assert len(rows) == 2
    assert rows[0]["id"] == "p1"
    assert rows[1]["id"] == "p2"


async def test_execute_returns_lastrowid(db):
    result = await db.execute(
        "INSERT INTO embedding_versions (provider, model, dimension, collection_name, is_active, created_at) "
        "VALUES (?, ?, ?, ?, ?, datetime('now'))",
        ("openai", "text-embedding-3-small", 1536, "paper_embeddings_v1", True),
    )
    assert result > 0


async def test_paper_sources_foreign_key(db):
    await db.execute(
        "INSERT INTO papers (id, title, abstract, published_date, first_seen_at, updated_at) "
        "VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))",
        ("p1", "Paper 1", "Abstract", "2026-04-01"),
    )
    await db.execute(
        "INSERT INTO paper_sources (paper_id, source_name, source_url, match_strategy, match_confidence, collected_at) "
        "VALUES (?, ?, ?, ?, ?, datetime('now'))",
        ("p1", "arxiv", "https://arxiv.org/abs/2026.12345", "arxiv_id", 1.0),
    )
    row = await db.fetch_one("SELECT * FROM paper_sources WHERE paper_id = ?", ("p1",))
    assert row["source_name"] == "arxiv"
