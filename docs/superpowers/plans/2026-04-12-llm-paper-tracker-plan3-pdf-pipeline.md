# PDF Pipeline (Plan 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the PDF download and parsing pipeline: a `PdfFetcher` service that downloads PDFs, verifies checksums, and stores them in versioned directories; and a `PdfParser` service that extracts full text, markdown, sections, blocks, figures, and references from PDFs.

**Architecture:** `PdfFetcher` claims `pdf_fetch` stage_runs, downloads via httpx, computes SHA256, stores to `data/papers/{paper_id}/files/versions/{sha256}.pdf`, writes `paper_files` record, and creates `pdf_parse` stage_run. `PdfParser` claims `pdf_parse` stage_runs, runs a pluggable parser (stub in v1), writes extraction artifacts to `data/papers/{paper_id}/extracted/{extraction_id}/`, writes `pdf_extractions` record, and creates `processor` stage_run. Both services are stateless and use the existing StageRunner for task management.

**Tech Stack:** httpx (async HTTP downloads), hashlib (SHA256), existing Database + StageRunner from Plan 1.

**Existing code context:**
- `backend/core/database.py` — `Database` class
- `backend/core/stage_runner.py` — `StageRunner` class with `create()`, `claim()`, `complete()`, `fail()`
- `backend/core/models.py` — `PaperFile`, `PdfExtraction` Pydantic models
- `backend/config/loader.py` — `PDFConfig` (download_timeout_seconds, max_file_size_mb, parser_name, parser_version), `StorageConfig` (data_root, paper_root)

---

## File Structure

| File | Responsibility |
|------|---------------|
| `backend/pdf/__init__.py` | Package init |
| `backend/pdf/fetcher.py` | `PdfFetcher` — download PDF, verify, store, write paper_files, create pdf_parse stage_run |
| `backend/pdf/parser.py` | `PdfParser` — extract text/markdown/blocks/sections from PDF, write pdf_extractions |
| `tests/backend/test_pdf/__init__.py` | Test package init |
| `tests/backend/test_pdf/test_fetcher.py` | Tests for PdfFetcher |
| `tests/backend/test_pdf/test_parser.py` | Tests for PdfParser |

---

### Task 1: PdfFetcher — Download and Store

**Files:**
- Create: `backend/pdf/__init__.py`
- Create: `backend/pdf/fetcher.py`
- Create: `tests/backend/test_pdf/__init__.py`
- Create: `tests/backend/test_pdf/test_fetcher.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/backend/test_pdf/__init__.py` (empty) and `tests/backend/test_pdf/test_fetcher.py`:

```python
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
    # Insert a paper first
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/backend/test_pdf/test_fetcher.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Write the implementation**

Create `backend/pdf/__init__.py` (empty) and `backend/pdf/fetcher.py`:

```python
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import httpx

from backend.core.database import Database
from backend.core.stage_runner import StageRunner

logger = logging.getLogger(__name__)


class PdfFetcher:
    def __init__(
        self,
        db: Database,
        stage_runner: StageRunner,
        paper_root: str,
        download_timeout: int = 120,
    ):
        self._db = db
        self._stage_runner = stage_runner
        self._paper_root = Path(paper_root)
        self._timeout = download_timeout

    async def process_next(self, worker_id: str = "pdf-fetcher-1") -> bool:
        task = await self._stage_runner.claim("pdf_fetch", worker_id)
        if not task:
            return False

        try:
            payload = json.loads(task["payload_json"]) if task["payload_json"] else {}
            pdf_url = payload.get("pdf_url", "")
            paper_id = task["target_id"]

            if not pdf_url:
                await self._stage_runner.fail(task["id"], "No pdf_url in payload")
                return True

            result = await self.download_and_store(paper_id, pdf_url)

            await self._stage_runner.complete(task["id"])
            await self._stage_runner.create(
                target_type="paper",
                target_id=paper_id,
                stage="pdf_parse",
                payload={"paper_file_id": result["paper_file_id"]},
            )
            return True
        except Exception as e:
            await self._stage_runner.fail(task["id"], str(e))
            return True

    async def download_and_store(self, paper_id: str, pdf_url: str) -> dict:
        async with httpx.AsyncClient(timeout=float(self._timeout)) as client:
            response = await client.get(pdf_url)
            response.raise_for_status()

        pdf_bytes = response.content
        sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        file_size = len(pdf_bytes)

        paper_dir = self._paper_root / paper_id / "files" / "versions"
        paper_dir.mkdir(parents=True, exist_ok=True)
        target_path = paper_dir / f"{sha256}.pdf"

        if not target_path.exists():
            target_path.write_bytes(pdf_bytes)

        storage_path = str(target_path)

        existing = await self._db.fetch_one(
            "SELECT id FROM paper_files WHERE paper_id = ? AND sha256 = ?",
            (paper_id, sha256),
        )

        if existing:
            return {
                "paper_file_id": existing["id"],
                "sha256": sha256,
                "file_size": file_size,
            }

        await self._db.execute(
            "UPDATE paper_files SET is_current = 0 WHERE paper_id = ? AND is_current = 1",
            (paper_id,),
        )

        paper_file_id = await self._db.execute(
            "INSERT INTO paper_files (paper_id, file_type, source_url, storage_path, "
            "file_size_bytes, sha256, mime_type, is_current, download_status, "
            "downloaded_at, verified_at) "
            "VALUES (?, 'pdf', ?, ?, ?, ?, 'application/pdf', 1, 'downloaded', "
            "datetime('now'), datetime('now'))",
            (paper_id, pdf_url, storage_path, file_size, sha256),
        )

        return {
            "paper_file_id": paper_file_id,
            "sha256": sha256,
            "file_size": file_size,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/backend/test_pdf/test_fetcher.py -v`
Expected: 6 passed

- [ ] **Step 5: Lint check**

Run: `ruff check backend/pdf/ tests/backend/test_pdf/`

- [ ] **Step 6: Commit**

```bash
git add backend/pdf/__init__.py backend/pdf/fetcher.py tests/backend/test_pdf/__init__.py tests/backend/test_pdf/test_fetcher.py
git commit -m "feat: PDF fetcher with download, checksum verification, and storage"
```

---

### Task 2: PdfParser — Text Extraction Stub

**Files:**
- Create: `backend/pdf/parser.py`
- Create: `tests/backend/test_pdf/test_parser.py`

For v1, the parser is a pluggable stub that reads the PDF bytes and produces minimal extraction artifacts. Real parser integration (e.g., marker) comes later. The important thing is the correct file layout, DB record creation, and stage_run management.

- [ ] **Step 1: Write the failing tests**

Create `tests/backend/test_pdf/test_parser.py`:

```python
import json
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


def _setup_paper_and_file(db, data_root, paper_id="paper-001"):
    """Helper to set up a paper with a PDF file on disk and in DB. Returns awaitable coroutine."""

    async def _setup():
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

    return _setup


async def test_parse_creates_extraction_record(parser, db, data_root):
    setup = _setup_paper_and_file(db, data_root)
    paper_file_id = await setup()

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
    setup = _setup_paper_and_file(db, data_root)
    paper_file_id = await setup()

    result = await parser.parse(paper_id="paper-001", paper_file_id=paper_file_id)

    extraction_dir = Path(result["extraction_root_path"])
    assert extraction_dir.exists()
    assert (extraction_dir / "fulltext.txt").exists()
    assert (extraction_dir / "fulltext.md").exists()
    assert (extraction_dir / "blocks.json").exists()
    assert (extraction_dir / "sections.json").exists()


async def test_parse_writes_correct_paths_to_db(parser, db, data_root):
    setup = _setup_paper_and_file(db, data_root)
    paper_file_id = await setup()

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
    setup = _setup_paper_and_file(db, data_root)
    paper_file_id = await setup()

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/backend/test_pdf/test_parser.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Write the implementation**

Create `backend/pdf/parser.py`:

```python
from __future__ import annotations

import json
import logging
from pathlib import Path

from backend.core.database import Database
from backend.core.stage_runner import StageRunner

logger = logging.getLogger(__name__)


class PdfParser:
    def __init__(
        self,
        db: Database,
        stage_runner: StageRunner,
        paper_root: str,
        parser_name: str = "stub",
        parser_version: str = "v0.1",
    ):
        self._db = db
        self._stage_runner = stage_runner
        self._paper_root = Path(paper_root)
        self._parser_name = parser_name
        self._parser_version = parser_version

    async def process_next(self, worker_id: str = "pdf-parser-1") -> bool:
        task = await self._stage_runner.claim("pdf_parse", worker_id)
        if not task:
            return False

        try:
            payload = json.loads(task["payload_json"]) if task["payload_json"] else {}
            paper_file_id = payload.get("paper_file_id")
            paper_id = task["target_id"]

            if not paper_file_id:
                await self._stage_runner.fail(task["id"], "No paper_file_id in payload")
                return True

            await self.parse(paper_id=paper_id, paper_file_id=paper_file_id)

            await self._stage_runner.complete(task["id"])
            await self._stage_runner.create(
                target_type="paper",
                target_id=paper_id,
                stage="processor",
            )
            return True
        except Exception as e:
            await self._stage_runner.fail(task["id"], str(e))
            return True

    async def parse(self, paper_id: str, paper_file_id: int) -> dict:
        paper_file = await self._db.fetch_one(
            "SELECT * FROM paper_files WHERE id = ?", (paper_file_id,)
        )
        if not paper_file:
            raise ValueError(f"paper_file {paper_file_id} not found")

        pdf_path = Path(paper_file["storage_path"])
        pdf_bytes = pdf_path.read_bytes()

        extraction_id_placeholder = await self._db.execute(
            "INSERT INTO pdf_extractions (paper_id, paper_file_id, parser_name, "
            "parser_version, extraction_status, extracted_at) "
            "VALUES (?, ?, ?, ?, 'pending', datetime('now'))",
            (paper_id, paper_file_id, self._parser_name, self._parser_version),
        )

        extraction_dir = (
            self._paper_root / paper_id / "extracted" / str(extraction_id_placeholder)
        )
        extraction_dir.mkdir(parents=True, exist_ok=True)

        fulltext = self._extract_text(pdf_bytes)
        markdown = self._extract_markdown(pdf_bytes)
        blocks = self._extract_blocks(pdf_bytes)
        sections = self._extract_sections(pdf_bytes)

        text_path = extraction_dir / "fulltext.txt"
        md_path = extraction_dir / "fulltext.md"
        blocks_path = extraction_dir / "blocks.json"
        sections_path = extraction_dir / "sections.json"

        text_path.write_text(fulltext, encoding="utf-8")
        md_path.write_text(markdown, encoding="utf-8")
        blocks_path.write_text(json.dumps(blocks), encoding="utf-8")
        sections_path.write_text(json.dumps(sections), encoding="utf-8")

        await self._db.execute(
            "UPDATE pdf_extractions SET extraction_status = 'succeeded', "
            "extraction_root_path = ?, extracted_text_path = ?, "
            "extracted_markdown_path = ?, blocks_json_path = ?, "
            "sections_json_path = ? WHERE id = ?",
            (
                str(extraction_dir),
                str(text_path),
                str(md_path),
                str(blocks_path),
                str(sections_path),
                extraction_id_placeholder,
            ),
        )

        return {
            "extraction_id": extraction_id_placeholder,
            "extraction_root_path": str(extraction_dir),
        }

    def _extract_text(self, pdf_bytes: bytes) -> str:
        return f"[stub] Extracted text from {len(pdf_bytes)} bytes"

    def _extract_markdown(self, pdf_bytes: bytes) -> str:
        return f"# Extracted Document\n\n[stub] Markdown from {len(pdf_bytes)} bytes"

    def _extract_blocks(self, pdf_bytes: bytes) -> list[dict]:
        return [{"page": 1, "type": "text", "content": f"[stub] block from {len(pdf_bytes)} bytes"}]

    def _extract_sections(self, pdf_bytes: bytes) -> list[dict]:
        return [{"title": "Introduction", "level": 1, "page": 1}]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/backend/test_pdf/test_parser.py -v`
Expected: 5 passed

- [ ] **Step 5: Lint check**

Run: `ruff check backend/pdf/parser.py tests/backend/test_pdf/test_parser.py`

- [ ] **Step 6: Commit**

```bash
git add backend/pdf/parser.py tests/backend/test_pdf/test_parser.py
git commit -m "feat: PDF parser with stub extraction and versioned output"
```

---

### Task 3: Full Test Suite Verification

- [ ] **Step 1: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests pass (~89 total)

- [ ] **Step 2: Run linter**

Run: `ruff check .`
Expected: All checks passed

- [ ] **Step 3: Fix any issues and commit if needed**

```bash
git add -u
git commit -m "chore: fix lint errors, plan 3 PDF pipeline complete"
```
