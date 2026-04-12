import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from backend.core.database import Database
from backend.core.stage_runner import StageRunner
from backend.pdf.fetcher import PdfFetcher


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
def fetcher(db, stage_runner, data_root):
    return PdfFetcher(
        db=db,
        stage_runner=stage_runner,
        paper_root=data_root,
        download_timeout=30,
    )


def _fake_pdf_bytes():
    return b"%PDF-1.4 fake pdf content for testing purposes"


async def test_download_and_store_creates_file(fetcher, db, data_root):
    await db.execute(
        "INSERT INTO papers (id, title, abstract, first_seen_at, updated_at) "
        "VALUES (?, ?, ?, datetime('now'), datetime('now'))",
        ("paper-001", "Test Paper", "Abstract"),
    )

    pdf_bytes = _fake_pdf_bytes()
    sha256 = hashlib.sha256(pdf_bytes).hexdigest()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = pdf_bytes
    mock_response.headers = {"content-type": "application/pdf"}
    mock_response.raise_for_status = MagicMock()

    with patch("backend.pdf.fetcher.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await fetcher.download_and_store(
            paper_id="paper-001",
            pdf_url="http://arxiv.org/pdf/2401.00001",
        )

    assert result["sha256"] == sha256
    assert result["file_size"] == len(pdf_bytes)

    stored_path = Path(data_root) / "paper-001" / "files" / "versions" / f"{sha256}.pdf"
    assert stored_path.exists()
    assert stored_path.read_bytes() == pdf_bytes


async def test_download_writes_paper_files_record(fetcher, db, data_root):
    await db.execute(
        "INSERT INTO papers (id, title, abstract, first_seen_at, updated_at) "
        "VALUES (?, ?, ?, datetime('now'), datetime('now'))",
        ("paper-001", "Test Paper", "Abstract"),
    )

    pdf_bytes = _fake_pdf_bytes()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = pdf_bytes
    mock_response.headers = {"content-type": "application/pdf"}
    mock_response.raise_for_status = MagicMock()

    with patch("backend.pdf.fetcher.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        await fetcher.download_and_store("paper-001", "http://arxiv.org/pdf/2401.00001")

    row = await db.fetch_one("SELECT * FROM paper_files WHERE paper_id = ?", ("paper-001",))
    assert row is not None
    assert row["download_status"] == "downloaded"
    assert row["is_current"] == 1
    assert row["file_size_bytes"] == len(pdf_bytes)


async def test_duplicate_sha256_is_idempotent(fetcher, db, data_root):
    await db.execute(
        "INSERT INTO papers (id, title, abstract, first_seen_at, updated_at) "
        "VALUES (?, ?, ?, datetime('now'), datetime('now'))",
        ("paper-001", "Test Paper", "Abstract"),
    )

    pdf_bytes = _fake_pdf_bytes()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = pdf_bytes
    mock_response.headers = {"content-type": "application/pdf"}
    mock_response.raise_for_status = MagicMock()

    with patch("backend.pdf.fetcher.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        await fetcher.download_and_store("paper-001", "http://arxiv.org/pdf/2401.00001")
        await fetcher.download_and_store("paper-001", "http://arxiv.org/pdf/2401.00001")

    rows = await db.fetch_all("SELECT * FROM paper_files WHERE paper_id = ?", ("paper-001",))
    assert len(rows) == 1


async def test_process_task_claims_and_completes(fetcher, db, stage_runner, data_root):
    await db.execute(
        "INSERT INTO papers (id, title, abstract, first_seen_at, updated_at) "
        "VALUES (?, ?, ?, datetime('now'), datetime('now'))",
        ("paper-001", "Test Paper", "Abstract"),
    )
    await stage_runner.create("paper", "paper-001", "pdf_fetch", {"pdf_url": "http://arxiv.org/pdf/2401.00001"})

    pdf_bytes = _fake_pdf_bytes()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = pdf_bytes
    mock_response.headers = {"content-type": "application/pdf"}
    mock_response.raise_for_status = MagicMock()

    with patch("backend.pdf.fetcher.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        processed = await fetcher.process_next()

    assert processed is True
    runs = await stage_runner.list_by_status("pdf_fetch", "succeeded")
    assert len(runs) == 1

    parse_runs = await stage_runner.list_by_status("pdf_parse", "pending")
    assert len(parse_runs) == 1


async def test_process_next_returns_false_when_no_tasks(fetcher):
    result = await fetcher.process_next()
    assert result is False
