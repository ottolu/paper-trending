from pathlib import Path

import pytest

from backend.core.database import Database
from backend.core.stage_runner import StageRunner
from backend.pdf.parser import PdfParser


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
def parser(db, stage_runner, data_root):
    return PdfParser(
        db=db,
        stage_runner=stage_runner,
        paper_root=data_root,
        parser_name="stub",
        parser_version="v0.1",
    )


async def _setup_paper_and_file(db, data_root, paper_id="paper-001"):
    await db.execute(
        "INSERT INTO papers (id, title, abstract, first_seen_at, updated_at) "
        "VALUES (?, ?, ?, datetime('now'), datetime('now'))",
        (paper_id, "Test Paper", "Abstract"),
    )
    pdf_path = Path(data_root) / paper_id / "files" / "versions" / "abc123.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"%PDF-1.4 test content for parsing")

    paper_file_id = await db.execute(
        "INSERT INTO paper_files (paper_id, file_type, storage_path, sha256, "
        "is_current, download_status, downloaded_at) "
        "VALUES (?, 'pdf', ?, 'abc123', 1, 'downloaded', datetime('now'))",
        (paper_id, str(pdf_path)),
    )
    return paper_file_id


async def test_parse_creates_extraction_record(parser, db, data_root):
    paper_file_id = await _setup_paper_and_file(db, data_root)

    result = await parser.parse(paper_id="paper-001", paper_file_id=paper_file_id)

    row = await db.fetch_one(
        "SELECT * FROM pdf_extractions WHERE paper_id = ?", ("paper-001",)
    )
    assert row is not None
    assert row["parser_name"] == "stub"
    assert row["parser_version"] == "v0.1"
    assert row["extraction_status"] == "succeeded"
    assert result["extraction_id"] == row["id"]


async def test_parse_creates_extraction_files(parser, db, data_root):
    paper_file_id = await _setup_paper_and_file(db, data_root)

    result = await parser.parse(paper_id="paper-001", paper_file_id=paper_file_id)

    extraction_dir = Path(result["extraction_root_path"])
    assert extraction_dir.exists()
    assert (extraction_dir / "fulltext.txt").exists()
    assert (extraction_dir / "fulltext.md").exists()
    assert (extraction_dir / "blocks.json").exists()
    assert (extraction_dir / "sections.json").exists()


async def test_parse_writes_correct_paths_to_db(parser, db, data_root):
    paper_file_id = await _setup_paper_and_file(db, data_root)

    await parser.parse(paper_id="paper-001", paper_file_id=paper_file_id)

    row = await db.fetch_one(
        "SELECT * FROM pdf_extractions WHERE paper_id = ?", ("paper-001",)
    )
    assert row["extracted_text_path"] is not None
    assert row["extracted_markdown_path"] is not None
    assert row["blocks_json_path"] is not None
    assert row["sections_json_path"] is not None
    assert Path(row["extracted_text_path"]).exists()


async def test_process_next_claims_and_completes(parser, db, stage_runner, data_root):
    paper_file_id = await _setup_paper_and_file(db, data_root)

    await stage_runner.create(
        "paper", "paper-001", "pdf_parse",
        {"paper_file_id": paper_file_id},
    )

    processed = await parser.process_next()
    assert processed is True

    runs = await stage_runner.list_by_status("pdf_parse", "succeeded")
    assert len(runs) == 1

    processor_runs = await stage_runner.list_by_status("processor", "pending")
    assert len(processor_runs) == 1


async def test_process_next_returns_false_when_no_tasks(parser):
    result = await parser.process_next()
    assert result is False
