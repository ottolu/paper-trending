from pathlib import Path

import pytest

from backend.core.database import Database
from backend.core.stage_runner import StageRunner
from backend.sync.service import ObsidianSyncService


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
def vault_path(tmp_path):
    vault = tmp_path / "obsidian_vault"
    vault.mkdir()
    return str(vault)


@pytest.fixture
def service(db, stage_runner, vault_path):
    return ObsidianSyncService(
        db=db,
        stage_runner=stage_runner,
        vault_path=vault_path,
        root_folder="LLM-Research",
    )


async def _setup_paper_with_analysis(db, paper_id="paper-001", first_seen="2024-01-15 08:00:00"):
    await db.execute(
        "INSERT INTO papers (id, arxiv_id, title, abstract, authors, arxiv_categories, "
        "published_date, first_seen_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
        (paper_id, "2401.00001", "Test Paper Title", "Abstract text here.",
         '["Author A", "Author B"]', '["cs.CL"]', "2024-01-14", first_seen),
    )

    analysis_run_id = await db.execute(
        "INSERT INTO analysis_runs (paper_id, factual_summary, methodology_inference, "
        "innovation_points, key_takeaways, score_total, score_breakdown, tags, "
        "evidence_level, analysis_basis, evidence_citations, confidence, status, analyzed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'succeeded', datetime('now'))",
        (paper_id, "本文研究缩放定律。", "实证评估方法。",
         '["创新点一"]', '["结论一"]', 8.5, '{}',
         '["scaling-laws"]', "strong", "full_text",
         '[{"claim": "缩放定律", "source": "full_text", "page": 3}]', 0.85),
    )

    await db.execute(
        "INSERT INTO paper_analysis (paper_id, active_analysis_run_id, active_analyzed_at) "
        "VALUES (?, ?, datetime('now'))",
        (paper_id, analysis_run_id),
    )

    await db.execute(
        "INSERT INTO paper_sources (paper_id, source_name, source_url, collected_at) "
        "VALUES (?, 'huggingface', 'https://huggingface.co/papers/2401.00001', datetime('now'))",
        (paper_id,),
    )

    return analysis_run_id


async def test_process_next_writes_paper_note(service, db, vault_path):
    await _setup_paper_with_analysis(db)
    await service._stage_runner.create("paper", "paper-001", "sync")

    result = await service.process_next()

    assert result is True
    vault = Path(vault_path) / "LLM-Research"
    # Find the paper note file
    md_files = list(vault.rglob("Test-Paper-Title.md"))
    assert len(md_files) == 1
    content = md_files[0].read_text(encoding="utf-8")
    assert "# Test Paper Title" in content
    assert "score: 8.5" in content
    assert "## 事实摘要" in content


async def test_process_next_writes_daily_summary(service, db, vault_path):
    await _setup_paper_with_analysis(db)
    await service._stage_runner.create("paper", "paper-001", "sync")

    await service.process_next()

    vault = Path(vault_path) / "LLM-Research"
    daily_files = list(vault.rglob("*-daily.md"))
    assert len(daily_files) == 1
    content = daily_files[0].read_text(encoding="utf-8")
    assert "论文日报" in content


async def test_process_next_records_sync_log(service, db, vault_path):
    await _setup_paper_with_analysis(db)
    await service._stage_runner.create("paper", "paper-001", "sync")

    await service.process_next()

    logs = await db.fetch_all("SELECT * FROM sync_log WHERE paper_id = ?", ("paper-001",))
    assert len(logs) >= 1
    paper_log = [row for row in logs if row["sync_type"] == "paper_note"]
    assert len(paper_log) == 1
    assert paper_log[0]["checksum"] != ""


async def test_idempotent_sync_skips_rewrite(service, db, vault_path):
    await _setup_paper_with_analysis(db)
    await service._stage_runner.create("paper", "paper-001", "sync")

    await service.process_next()

    # Create another sync task for the same paper
    await db.execute(
        "DELETE FROM stage_run_attempts WHERE stage_run_id IN "
        "(SELECT id FROM stage_runs WHERE target_id = 'paper-001' AND stage = 'sync')"
    )
    await db.execute(
        "DELETE FROM stage_runs WHERE target_id = 'paper-001' AND stage = 'sync'"
    )
    await service._stage_runner.create("paper", "paper-001", "sync")

    await service.process_next()

    # Should still only have 1 sync_log entry for paper_note (same checksum)
    logs = await db.fetch_all(
        "SELECT * FROM sync_log WHERE paper_id = ? AND sync_type = 'paper_note'",
        ("paper-001",),
    )
    assert len(logs) == 1


async def test_process_next_returns_false_when_no_tasks(service):
    result = await service.process_next()
    assert result is False


async def test_file_placed_in_correct_week_directory(service, db, vault_path):
    # first_seen_at = 2024-01-15 → ISO week 2024-W03, date folder 2024-01-15
    await _setup_paper_with_analysis(db, first_seen="2024-01-15 08:00:00")
    await service._stage_runner.create("paper", "paper-001", "sync")

    await service.process_next()

    vault = Path(vault_path) / "LLM-Research"
    md_files = list(vault.rglob("Test-Paper-Title.md"))
    assert len(md_files) == 1
    path_str = str(md_files[0])
    assert "2024-W03" in path_str
    assert "2024-01-15" in path_str


async def test_process_marks_stage_succeeded(service, db, stage_runner, vault_path):
    await _setup_paper_with_analysis(db)
    await stage_runner.create("paper", "paper-001", "sync")

    await service.process_next()

    runs = await stage_runner.list_by_status("sync", "succeeded")
    assert len(runs) == 1
