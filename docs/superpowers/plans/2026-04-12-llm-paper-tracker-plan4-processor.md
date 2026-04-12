# Processor (Plan 4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Processor service that claims `processor` stage_runs, reads PDF extraction outputs, chunks full text for LLM consumption, assembles a reading manifest (metadata + abstract + chunks + section map), computes a manifest hash, writes it to the cache directory, and creates `analyzer` stage_runs.

**Architecture:** A `ProcessorService` claims tasks via StageRunner, reads `pdf_extractions` for the paper, splits text into chunks, writes a `chunk_manifest.json` to `data/papers/{paper_id}/cache/{hash}.json`, and enqueues the analyzer stage. Chunking is a simple function (split by paragraph/token limit). Dedup is by arXiv ID check.

**Tech Stack:** hashlib (manifest hash), json, existing Database + StageRunner from Plan 1.

---

## File Structure

| File | Responsibility |
|------|---------------|
| `backend/processor/__init__.py` | Package init |
| `backend/processor/chunker.py` | `chunk_text()` — split text into LLM-consumable chunks |
| `backend/processor/service.py` | `ProcessorService` — orchestrate: claim task → read extraction → chunk → write manifest → create analyzer stage_run |
| `tests/backend/test_processor/__init__.py` | Test package init |
| `tests/backend/test_processor/test_chunker.py` | Tests for chunker |
| `tests/backend/test_processor/test_service.py` | Tests for ProcessorService |

---

### Task 1: Text Chunker

**Files:**
- Create: `backend/processor/__init__.py`
- Create: `backend/processor/chunker.py`
- Create: `tests/backend/test_processor/__init__.py`
- Create: `tests/backend/test_processor/test_chunker.py`

- [ ] **Step 1: Write the failing tests**

```python
from backend.processor.chunker import chunk_text


def test_short_text_single_chunk():
    text = "This is a short paragraph."
    chunks = chunk_text(text, max_chars=1000)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_long_text_splits_by_paragraph():
    paragraphs = ["Paragraph one. " * 20, "Paragraph two. " * 20, "Paragraph three. " * 20]
    text = "\n\n".join(paragraphs)
    chunks = chunk_text(text, max_chars=400)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert len(chunk) <= 400 + 50  # allow small overflow for word boundaries


def test_empty_text_returns_empty():
    assert chunk_text("", max_chars=1000) == []


def test_respects_overlap():
    text = "A. " * 100 + "\n\n" + "B. " * 100
    chunks = chunk_text(text, max_chars=200, overlap_chars=50)
    assert len(chunks) >= 2


def test_chunks_have_metadata():
    text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    chunks = chunk_text(text, max_chars=30, return_with_metadata=True)
    assert len(chunks) >= 2
    assert all(isinstance(c, dict) for c in chunks)
    assert all("text" in c and "index" in c for c in chunks)
```

- [ ] **Step 2: Write the implementation**

```python
from __future__ import annotations


def chunk_text(
    text: str,
    max_chars: int = 4000,
    overlap_chars: int = 200,
    return_with_metadata: bool = False,
) -> list[str] | list[dict]:
    if not text.strip():
        return []

    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if current and len(current) + len(para) + 2 > max_chars:
            chunks.append(current)
            if overlap_chars > 0 and len(current) > overlap_chars:
                current = current[-overlap_chars:] + "\n\n" + para
            else:
                current = para
        else:
            current = current + "\n\n" + para if current else para

    if current:
        chunks.append(current)

    if return_with_metadata:
        return [{"text": c, "index": i, "char_count": len(c)} for i, c in enumerate(chunks)]
    return chunks
```

- [ ] **Step 3: Run tests, lint, commit**

```bash
pytest tests/backend/test_processor/test_chunker.py -v
ruff check backend/processor/ tests/backend/test_processor/
git commit -m "feat: text chunker for LLM-consumable paragraph splitting"
```

---

### Task 2: ProcessorService

**Files:**
- Create: `backend/processor/service.py`
- Create: `tests/backend/test_processor/test_service.py`

- [ ] **Step 1: Write the failing tests**

```python
import hashlib
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

    extraction_id = await db.execute(
        "INSERT INTO pdf_extractions (paper_id, paper_file_id, parser_name, parser_version, "
        "extraction_status, extracted_text_path, sections_json_path, extraction_root_path) "
        "VALUES (?, ?, 'stub', 'v0.1', 'succeeded', ?, ?, ?)",
        (paper_id, paper_file_id, str(text_path), str(sections_path), str(extraction_dir)),
    )
    return extraction_id


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
    """Papers without PDF extraction should still get a manifest (abstract-only)."""
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
```

- [ ] **Step 2: Write the implementation**

```python
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from backend.core.database import Database
from backend.core.stage_runner import StageRunner
from backend.processor.chunker import chunk_text

logger = logging.getLogger(__name__)


class ProcessorService:
    def __init__(
        self,
        db: Database,
        stage_runner: StageRunner,
        paper_root: str,
        max_chunk_chars: int = 4000,
    ):
        self._db = db
        self._stage_runner = stage_runner
        self._paper_root = Path(paper_root)
        self._max_chunk_chars = max_chunk_chars

    async def process_next(self, worker_id: str = "processor-1") -> bool:
        task = await self._stage_runner.claim("processor", worker_id)
        if not task:
            return False

        try:
            paper_id = task["target_id"]
            manifest = await self._build_manifest(paper_id)

            manifest_json = json.dumps(manifest, ensure_ascii=False, sort_keys=True)
            manifest_hash = hashlib.sha256(manifest_json.encode()).hexdigest()

            cache_dir = self._paper_root / paper_id / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            manifest_path = cache_dir / f"{manifest_hash}.json"
            manifest_path.write_text(manifest_json, encoding="utf-8")

            await self._stage_runner.complete(task["id"])
            await self._stage_runner.create(
                target_type="paper",
                target_id=paper_id,
                stage="analyzer",
                payload={
                    "chunk_manifest_path": str(manifest_path),
                    "chunk_manifest_hash": manifest_hash,
                    "analysis_basis": manifest["analysis_basis"],
                },
            )
            return True
        except Exception as e:
            await self._stage_runner.fail(task["id"], str(e))
            return True

    async def _build_manifest(self, paper_id: str) -> dict:
        paper = await self._db.fetch_one("SELECT * FROM papers WHERE id = ?", (paper_id,))
        if not paper:
            raise ValueError(f"Paper {paper_id} not found")

        authors = json.loads(paper["authors"]) if paper["authors"] else []
        categories = json.loads(paper["arxiv_categories"]) if paper["arxiv_categories"] else []

        extraction = await self._db.fetch_one(
            "SELECT * FROM pdf_extractions WHERE paper_id = ? AND extraction_status = 'succeeded' "
            "ORDER BY id DESC LIMIT 1",
            (paper_id,),
        )

        analysis_basis = "abstract_only"
        chunks = []
        sections = []

        if extraction and extraction["extracted_text_path"]:
            text_path = Path(extraction["extracted_text_path"])
            if text_path.exists():
                full_text = text_path.read_text(encoding="utf-8")
                chunks = chunk_text(full_text, max_chars=self._max_chunk_chars, return_with_metadata=True)
                analysis_basis = "full_text"

            if extraction["sections_json_path"]:
                sections_path = Path(extraction["sections_json_path"])
                if sections_path.exists():
                    sections = json.loads(sections_path.read_text(encoding="utf-8"))

        return {
            "paper_id": paper_id,
            "title": paper["title"],
            "abstract": paper["abstract"],
            "authors": authors,
            "arxiv_categories": categories,
            "published_date": paper["published_date"],
            "analysis_basis": analysis_basis,
            "chunks": chunks,
            "sections": sections,
        }
```

- [ ] **Step 3: Run tests, lint, commit**

```bash
pytest tests/backend/test_processor/test_service.py -v
ruff check backend/processor/ tests/backend/test_processor/
git commit -m "feat: processor service with chunking and manifest generation"
```

---

### Task 3: Full Test Suite Verification

- [ ] **Step 1: Run all tests**

Run: `pytest tests/ -v`
Expected: All pass (~98 total)

- [ ] **Step 2: Run linter**

Run: `ruff check .`
Expected: All checks passed
