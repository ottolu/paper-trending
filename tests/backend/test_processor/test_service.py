import json
from pathlib import Path

import pytest

from backend.core.database import Database
from backend.core.stage_runner import StageRunner
from backend.processor.service import ProcessorService


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
def data_root(tmp_path):
    root = tmp_path / "data" / "papers"
    root.mkdir(parents=True)
    return str(root)


@pytest.fixture
def service(db, stage_runner, data_root):
    return ProcessorService(db=db, stage_runner=stage_runner, paper_root=data_root)


async def _setup_paper_with_extraction(db, data_root, paper_id="paper-001"):
    await db.execute(
        "INSERT INTO papers (id, title, abstract, authors, arxiv_categories, first_seen_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))",
        (paper_id, "Test Paper", "This is the abstract.", '["Author A"]', '["cs.CL"]'),
    )
    pdf_path = Path(data_root) / paper_id / "files" / "versions" / "abc123.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"%PDF test")

    paper_file_id = await db.execute(
        "INSERT INTO paper_files (paper_id, file_type, storage_path, sha256, "
        "is_current, download_status) VALUES (?, 'pdf', ?, 'abc123', 1, 'downloaded')",
        (paper_id, str(pdf_path)),
    )

    extraction_dir = Path(data_root) / paper_id / "extracted" / "1"
    extraction_dir.mkdir(parents=True, exist_ok=True)
    text_path = extraction_dir / "fulltext.txt"
    text_path.write_text("Introduction paragraph.\n\nMethods paragraph.\n\nResults paragraph.")
    sections_path = extraction_dir / "sections.json"
    sections_path.write_text(json.dumps([{"title": "Introduction", "level": 1}]))

    await db.execute(
        "INSERT INTO pdf_extractions (paper_id, paper_file_id, parser_name, parser_version, "
        "extraction_status, extracted_text_path, sections_json_path, extraction_root_path) "
        "VALUES (?, ?, 'stub', 'v0.1', 'succeeded', ?, ?, ?)",
        (paper_id, paper_file_id, str(text_path), str(sections_path), str(extraction_dir)),
    )


async def test_process_builds_manifest(service, db, data_root):
    await _setup_paper_with_extraction(db, data_root)
    await service._stage_runner.create("paper", "paper-001", "processor")

    await service.process_next()

    cache_dir = Path(data_root) / "paper-001" / "cache"
    assert cache_dir.exists()
    manifests = list(cache_dir.glob("*.json"))
    assert len(manifests) == 1

    manifest = json.loads(manifests[0].read_text())
    assert manifest["paper_id"] == "paper-001"
    assert manifest["title"] == "Test Paper"
    assert manifest["abstract"] == "This is the abstract."
    assert "chunks" in manifest
    assert len(manifest["chunks"]) >= 1


async def test_process_creates_analyzer_stage_run(service, db, stage_runner, data_root):
    await _setup_paper_with_extraction(db, data_root)
    await stage_runner.create("paper", "paper-001", "processor")

    await service.process_next()

    analyzer_runs = await stage_runner.list_by_status("analyzer", "pending")
    assert len(analyzer_runs) == 1
    assert analyzer_runs[0]["target_id"] == "paper-001"


async def test_process_marks_task_succeeded(service, db, stage_runner, data_root):
    await _setup_paper_with_extraction(db, data_root)
    await stage_runner.create("paper", "paper-001", "processor")

    await service.process_next()

    runs = await stage_runner.list_by_status("processor", "succeeded")
    assert len(runs) == 1


async def test_process_next_returns_false_when_no_tasks(service):
    result = await service.process_next()
    assert result is False


async def test_process_without_extraction_still_creates_manifest(service, db, data_root):
    await db.execute(
        "INSERT INTO papers (id, title, abstract, authors, arxiv_categories, first_seen_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))",
        ("paper-002", "No PDF Paper", "Abstract only.", '["Author B"]', '["cs.AI"]'),
    )
    await service._stage_runner.create("paper", "paper-002", "processor")

    await service.process_next()

    cache_dir = Path(data_root) / "paper-002" / "cache"
    manifests = list(cache_dir.glob("*.json"))
    assert len(manifests) == 1
    manifest = json.loads(manifests[0].read_text())
    assert manifest["analysis_basis"] == "abstract_only"
