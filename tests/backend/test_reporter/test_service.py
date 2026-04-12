import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.core.database import Database
from backend.core.stage_runner import StageRunner
from backend.reporter.service import ReporterService


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
def mock_llm():
    client = AsyncMock()
    client.chat = AsyncMock(return_value=(
        "## 本周趋势\n本周关注点集中在RLHF领域。\n\n"
        "## 领域动态\n### #rlhf\n本周活跃。"
    ))
    return client


@pytest.fixture
def mock_vector_store():
    store = MagicMock()
    store.get = MagicMock(return_value={
        "ids": [["paper-001", "paper-002", "paper-003"]],
        "embeddings": [[[0.1] * 8, [0.2] * 8, [0.3] * 8]],
    })
    return store


@pytest.fixture
def service(db, stage_runner, mock_llm, mock_vector_store):
    return ReporterService(
        db=db,
        stage_runner=stage_runner,
        llm_client=mock_llm,
        vector_store=mock_vector_store,
        embedding_collection="paper_embeddings_v1",
        embedding_version_id=1,
    )


async def _setup_papers_with_analysis(db, count=5):
    # Insert embedding_version for FK
    await db.execute(
        "INSERT INTO embedding_versions (id, provider, model, dimension, collection_name, "
        "is_active, created_at) VALUES (1, 'openai', 'text-embedding-3-small', 8, 'test', 1, datetime('now'))"
    )
    for i in range(count):
        paper_id = f"paper-{i:03d}"
        await db.execute(
            "INSERT INTO papers (id, arxiv_id, title, abstract, authors, arxiv_categories, "
            "published_date, first_seen_at, updated_at) "
            "VALUES (?, ?, ?, ?, '[]', '[]', '2024-01-15', '2024-01-16 08:00:00', datetime('now'))",
            (paper_id, f"2401.{i:05d}", f"Paper {i}", f"Abstract {i}"),
        )
        ar_id = await db.execute(
            "INSERT INTO analysis_runs (paper_id, factual_summary, methodology_inference, "
            "innovation_points, key_takeaways, score_total, score_breakdown, tags, "
            "evidence_level, analysis_basis, evidence_citations, confidence, status, analyzed_at) "
            "VALUES (?, ?, '方法', '[]', '[]', ?, '{}', ?, 'strong', 'full_text', '[]', 0.8, "
            "'succeeded', '2024-01-16 10:00:00')",
            (paper_id, f"摘要{i}", 7.0 + i * 0.5, json.dumps([f"tag-{i % 3}"])),
        )
        await db.execute(
            "INSERT INTO paper_analysis (paper_id, active_analysis_run_id, active_analyzed_at) "
            "VALUES (?, ?, '2024-01-16 10:00:00')",
            (paper_id, ar_id),
        )


async def test_generate_report_creates_weekly_report(service, db, mock_vector_store):
    await _setup_papers_with_analysis(db, count=5)

    report_id = await service.generate_report(
        week_start="2024-01-15",
        week_end="2024-01-21",
    )

    assert report_id is not None
    row = await db.fetch_one("SELECT * FROM weekly_reports WHERE id = ?", (report_id,))
    assert row is not None
    assert row["week_start"] == "2024-01-15"
    assert row["week_end"] == "2024-01-21"
    assert row["is_current"] is True or row["is_current"] == 1
    assert row["report_content"] is not None
    assert len(row["report_content"]) > 0


async def test_generate_report_calls_llm(service, db, mock_llm, mock_vector_store):
    await _setup_papers_with_analysis(db, count=5)

    await service.generate_report(week_start="2024-01-15", week_end="2024-01-21")

    mock_llm.chat.assert_called_once()


async def test_generate_report_creates_sync_stage_run(service, db, stage_runner, mock_vector_store):
    await _setup_papers_with_analysis(db, count=5)

    report_id = await service.generate_report(week_start="2024-01-15", week_end="2024-01-21")

    sync_runs = await stage_runner.list_by_status("sync", "pending")
    assert len(sync_runs) == 1
    assert sync_runs[0]["target_type"] == "report"
    assert sync_runs[0]["target_id"] == str(report_id)


async def test_generate_report_runs_clustering(service, db, mock_vector_store):
    await _setup_papers_with_analysis(db, count=5)

    report_id = await service.generate_report(week_start="2024-01-15", week_end="2024-01-21")

    row = await db.fetch_one("SELECT * FROM weekly_reports WHERE id = ?", (report_id,))
    assert row["cluster_run_id"] is not None

    cluster_run = await db.fetch_one(
        "SELECT * FROM cluster_runs WHERE id = ?", (row["cluster_run_id"],)
    )
    assert cluster_run is not None
    assert cluster_run["run_type"] == "stable"


async def test_generate_report_with_no_papers(service, db, mock_vector_store):
    # Insert embedding_version for FK
    await db.execute(
        "INSERT INTO embedding_versions (id, provider, model, dimension, collection_name, "
        "is_active, created_at) VALUES (1, 'openai', 'text-embedding-3-small', 8, 'test', 1, datetime('now'))"
    )
    mock_vector_store.get = MagicMock(return_value={"ids": [[]], "embeddings": [[]]})

    report_id = await service.generate_report(week_start="2024-01-15", week_end="2024-01-21")

    assert report_id is not None
    row = await db.fetch_one("SELECT * FROM weekly_reports WHERE id = ?", (report_id,))
    assert row is not None
