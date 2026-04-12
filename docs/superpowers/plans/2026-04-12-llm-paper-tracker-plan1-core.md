# Plan 1: Core Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the project skeleton, configuration system, database schema with stage-based task management, LLM/Embedding clients, and ChromaDB vector store — the foundation all other plans depend on.

**Architecture:** A Python backend using FastAPI, SQLite (via aiosqlite) for structured data, ChromaDB for vector storage, and a lease-based stage_runs system for task orchestration. Configuration is YAML-based with environment variable interpolation. All async.

**Tech Stack:** Python 3.11+, FastAPI, aiosqlite, ChromaDB, OpenAI SDK, PyYAML, pytest + pytest-asyncio

---

## File Structure

```
paper-trending/
├── pyproject.toml                          # Project metadata, dependencies, tool config
├── backend/
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.yaml                   # Default configuration
│   │   └── loader.py                       # YAML config loader with env var interpolation
│   ├── core/
│   │   ├── __init__.py
│   │   ├── database.py                     # SQLite connection pool, migration runner
│   │   ├── schema.sql                      # Full DDL for all tables
│   │   ├── models.py                       # Pydantic models for all entities
│   │   ├── stage_runner.py                 # Stage runs CRUD + lease manager
│   │   ├── llm_client.py                   # Unified LLM client (OpenAI protocol)
│   │   ├── embedding_client.py             # Unified Embedding client (OpenAI protocol)
│   │   └── vector_store.py                 # ChromaDB wrapper with version isolation
│   └── main.py                             # FastAPI app entry point (minimal)
├── tests/
│   ├── __init__.py
│   ├── conftest.py                         # Shared fixtures (tmp db, tmp dirs, etc.)
│   ├── backend/
│   │   ├── __init__.py
│   │   ├── test_config.py
│   │   ├── test_database.py
│   │   ├── test_models.py
│   │   ├── test_stage_runner.py
│   │   ├── test_llm_client.py
│   │   ├── test_embedding_client.py
│   │   └── test_vector_store.py
│   └── fixtures/
│       └── settings_test.yaml
└── data/                                   # Runtime data (gitignored)
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `backend/__init__.py`
- Create: `backend/config/__init__.py`
- Create: `backend/core/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/backend/__init__.py`
- Create: `.gitignore`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "llm-paper-tracker"
version = "0.1.0"
description = "LLM research paper tracking, analysis, and trend detection"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "aiosqlite>=0.20.0",
    "chromadb>=0.5.0",
    "openai>=1.40.0",
    "pyyaml>=6.0",
    "pydantic>=2.0",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=5.0",
    "ruff>=0.5.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
pythonpath = ["."]

[tool.ruff]
target-version = "py311"
line-length = 100
```

- [ ] **Step 2: Create package init files and .gitignore**

`backend/__init__.py`, `backend/config/__init__.py`, `backend/core/__init__.py`, `tests/__init__.py`, `tests/backend/__init__.py` — all empty files.

`.gitignore`:

```
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
data/
*.db
.env
.venv/
node_modules/
dist/
```

- [ ] **Step 3: Create data directory**

```bash
mkdir -p data
```

- [ ] **Step 4: Install dependencies and verify**

```bash
pip install -e ".[dev]"
pytest --co -q
```

Expected: `no tests ran` (no test files yet), exit 0.

- [ ] **Step 5: Commit**

```bash
git init
git add pyproject.toml backend/ tests/ .gitignore
git commit -m "chore: project scaffolding with dependencies"
```

---

## Task 2: Configuration System

**Files:**
- Create: `backend/config/settings.yaml`
- Create: `backend/config/loader.py`
- Create: `tests/fixtures/settings_test.yaml`
- Create: `tests/backend/test_config.py`

- [ ] **Step 1: Write the failing test**

`tests/backend/test_config.py`:

```python
import os
from pathlib import Path

import pytest

from backend.config.loader import load_config, AppConfig


@pytest.fixture
def test_config_path():
    return Path(__file__).parent.parent / "fixtures" / "settings_test.yaml"


def test_load_config_returns_app_config(test_config_path):
    config = load_config(test_config_path)
    assert isinstance(config, AppConfig)


def test_load_config_reads_llm_settings(test_config_path):
    config = load_config(test_config_path)
    assert config.llm.model == "gpt-5.4"
    assert config.llm.base_url == "https://api.openai.com/v1"


def test_load_config_reads_embedding_settings(test_config_path):
    config = load_config(test_config_path)
    assert config.embedding.model == "text-embedding-3-small"
    assert config.embedding.active_version_id == 1


def test_load_config_reads_obsidian_settings(test_config_path):
    config = load_config(test_config_path)
    assert config.obsidian.root_folder == "LLM-Research"


def test_load_config_reads_storage_settings(test_config_path):
    config = load_config(test_config_path)
    assert config.storage.data_root == "./data"


def test_load_config_reads_pdf_settings(test_config_path):
    config = load_config(test_config_path)
    assert config.pdf.download_timeout_seconds == 120
    assert config.pdf.parser_name == "marker"


def test_load_config_interpolates_env_vars(test_config_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-123")
    config = load_config(test_config_path)
    assert config.llm.api_key == "sk-test-key-123"


def test_load_config_missing_env_var_raises(test_config_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        load_config(test_config_path)
```

- [ ] **Step 2: Create test fixture YAML**

`tests/fixtures/settings_test.yaml`:

```yaml
llm:
  base_url: "https://api.openai.com/v1"
  api_key: "${OPENAI_API_KEY}"
  model: "gpt-5.4"
  prompt_version: "analysis_v1"

embedding:
  base_url: "https://api.openai.com/v1"
  api_key: "${OPENAI_API_KEY}"
  model: "text-embedding-3-small"
  active_version_id: 1

obsidian:
  vault_path: "/tmp/test-vault"
  root_folder: "LLM-Research"

storage:
  data_root: "./data"
  paper_root: "./data/papers"

pdf:
  download_timeout_seconds: 120
  max_file_size_mb: 100
  parser_name: "marker"
  parser_version: "v1"
  keep_raw_pdf: true

arxiv:
  categories:
    - "cs.CL"
    - "cs.AI"
    - "cs.LG"
  request_interval_seconds: 3

scheduler:
  collector_cron: "0 2 * * *"
  reporter_cron: "0 9 * * 1"
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/backend/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.config.loader'`

- [ ] **Step 4: Write the implementation**

`backend/config/loader.py`:

```python
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


class LLMConfig(BaseModel):
    base_url: str
    api_key: str
    model: str
    prompt_version: str = "analysis_v1"


class EmbeddingConfig(BaseModel):
    base_url: str
    api_key: str
    model: str
    active_version_id: int = 1


class ObsidianConfig(BaseModel):
    vault_path: str
    root_folder: str = "LLM-Research"


class StorageConfig(BaseModel):
    data_root: str = "./data"
    paper_root: str = "./data/papers"


class PDFConfig(BaseModel):
    download_timeout_seconds: int = 120
    max_file_size_mb: int = 100
    parser_name: str = "marker"
    parser_version: str = "v1"
    keep_raw_pdf: bool = True


class ArxivConfig(BaseModel):
    categories: list[str] = ["cs.CL", "cs.AI", "cs.LG"]
    request_interval_seconds: int = 3


class SchedulerConfig(BaseModel):
    collector_cron: str = "0 2 * * *"
    reporter_cron: str = "0 9 * * 1"


class AppConfig(BaseModel):
    llm: LLMConfig
    embedding: EmbeddingConfig
    obsidian: ObsidianConfig
    storage: StorageConfig = StorageConfig()
    pdf: PDFConfig = PDFConfig()
    arxiv: ArxivConfig = ArxivConfig()
    scheduler: SchedulerConfig = SchedulerConfig()


_ENV_VAR_PATTERN = re.compile(r"\$\{(\w+)\}")


def _interpolate_env_vars(data: Any) -> Any:
    if isinstance(data, str):
        match = _ENV_VAR_PATTERN.fullmatch(data)
        if match:
            var_name = match.group(1)
            value = os.environ.get(var_name)
            if value is None:
                raise ValueError(
                    f"Environment variable {var_name} is required but not set"
                )
            return value
        return data
    if isinstance(data, dict):
        return {k: _interpolate_env_vars(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_interpolate_env_vars(item) for item in data]
    return data


def load_config(path: Path | str) -> AppConfig:
    path = Path(path)
    with open(path) as f:
        raw = yaml.safe_load(f)
    resolved = _interpolate_env_vars(raw)
    return AppConfig(**resolved)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/backend/test_config.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 6: Create the default settings.yaml**

`backend/config/settings.yaml`:

```yaml
llm:
  base_url: "https://api.openai.com/v1"
  api_key: "${OPENAI_API_KEY}"
  model: "gpt-5.4"
  prompt_version: "analysis_v1"

embedding:
  base_url: "https://api.openai.com/v1"
  api_key: "${OPENAI_API_KEY}"
  model: "text-embedding-3-small"
  active_version_id: 1

obsidian:
  vault_path: "${OBSIDIAN_VAULT_PATH}"
  root_folder: "LLM-Research"

storage:
  data_root: "./data"
  paper_root: "./data/papers"

pdf:
  download_timeout_seconds: 120
  max_file_size_mb: 100
  parser_name: "marker"
  parser_version: "v1"
  keep_raw_pdf: true

arxiv:
  categories:
    - "cs.CL"
    - "cs.AI"
    - "cs.LG"
  request_interval_seconds: 3

scheduler:
  collector_cron: "0 2 * * *"
  reporter_cron: "0 9 * * 1"
```

- [ ] **Step 7: Commit**

```bash
git add backend/config/ tests/backend/test_config.py tests/fixtures/
git commit -m "feat: configuration system with YAML loading and env var interpolation"
```

---

## Task 3: Database Schema and Connection

**Files:**
- Create: `backend/core/schema.sql`
- Create: `backend/core/database.py`
- Create: `tests/conftest.py`
- Create: `tests/backend/test_database.py`

- [ ] **Step 1: Write the failing test**

`tests/backend/test_database.py`:

```python
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
```

- [ ] **Step 2: Write conftest.py with shared fixtures**

`tests/conftest.py`:

```python
import pytest

from backend.core.database import Database


@pytest.fixture
async def test_db(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    await db.initialize()
    yield db
    await db.close()
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/backend/test_database.py -v
```

Expected: `ModuleNotFoundError: No module named 'backend.core.database'`

- [ ] **Step 4: Write schema.sql**

`backend/core/schema.sql`:

```sql
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS papers (
    id TEXT PRIMARY KEY,
    arxiv_id TEXT UNIQUE,
    title TEXT NOT NULL,
    authors JSON,
    abstract TEXT NOT NULL,
    arxiv_categories JSON,
    published_date DATE,
    first_seen_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS paper_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id TEXT NOT NULL REFERENCES papers(id),
    source_name TEXT NOT NULL,
    source_url TEXT,
    source_record_id TEXT,
    match_strategy TEXT,
    match_confidence REAL,
    hf_likes INTEGER,
    hf_discussions INTEGER,
    collected_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS paper_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id TEXT NOT NULL REFERENCES papers(id),
    file_type TEXT NOT NULL DEFAULT 'pdf',
    source_url TEXT,
    storage_path TEXT,
    file_size_bytes INTEGER,
    sha256 TEXT,
    mime_type TEXT DEFAULT 'application/pdf',
    is_current BOOLEAN DEFAULT FALSE,
    download_status TEXT DEFAULT 'pending',
    downloaded_at DATETIME,
    verified_at DATETIME,
    UNIQUE(paper_id, sha256)
);

CREATE TABLE IF NOT EXISTS pdf_extractions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id TEXT NOT NULL REFERENCES papers(id),
    paper_file_id INTEGER NOT NULL REFERENCES paper_files(id),
    parser_name TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    extraction_status TEXT DEFAULT 'pending',
    page_count INTEGER,
    extraction_root_path TEXT,
    extracted_text_path TEXT,
    extracted_markdown_path TEXT,
    blocks_json_path TEXT,
    sections_json_path TEXT,
    figures_json_path TEXT,
    references_json_path TEXT,
    parse_quality_score REAL,
    extracted_at DATETIME
);

CREATE TABLE IF NOT EXISTS stage_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    logical_job_key TEXT UNIQUE NOT NULL,
    attempt_no INTEGER NOT NULL DEFAULT 0,
    worker_id TEXT,
    lease_expires_at DATETIME,
    idempotency_key TEXT,
    payload_json JSON,
    last_error TEXT,
    last_error_at DATETIME,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS stage_run_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stage_run_id INTEGER NOT NULL REFERENCES stage_runs(id),
    attempt_no INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    worker_id TEXT NOT NULL,
    lease_expires_at DATETIME NOT NULL,
    input_hash TEXT,
    started_at DATETIME NOT NULL,
    finished_at DATETIME,
    error_message TEXT,
    UNIQUE(stage_run_id, attempt_no)
);

CREATE TABLE IF NOT EXISTS analysis_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id TEXT NOT NULL REFERENCES papers(id),
    paper_file_id INTEGER REFERENCES paper_files(id),
    pdf_extraction_id INTEGER REFERENCES pdf_extractions(id),
    chunk_manifest_path TEXT,
    chunk_manifest_hash TEXT,
    input_hash TEXT,
    factual_summary TEXT,
    methodology_inference TEXT,
    innovation_points JSON,
    key_takeaways JSON,
    score_total REAL,
    score_breakdown JSON,
    tags JSON,
    evidence_level TEXT,
    analysis_basis TEXT NOT NULL DEFAULT 'abstract_only',
    evidence_citations JSON,
    confidence REAL,
    analysis_model TEXT,
    prompt_version TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    analyzed_at DATETIME
);

CREATE TABLE IF NOT EXISTS paper_analysis (
    paper_id TEXT PRIMARY KEY REFERENCES papers(id),
    active_analysis_run_id INTEGER NOT NULL REFERENCES analysis_runs(id),
    active_paper_file_id INTEGER REFERENCES paper_files(id),
    active_pdf_extraction_id INTEGER REFERENCES pdf_extractions(id),
    active_analyzed_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS embedding_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    dimension INTEGER NOT NULL,
    collection_name TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS cluster_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_type TEXT NOT NULL,
    embedding_version_id INTEGER NOT NULL REFERENCES embedding_versions(id),
    window_start DATE,
    window_end DATE,
    paper_count INTEGER,
    algorithm_name TEXT NOT NULL DEFAULT 'hdbscan',
    algorithm_version TEXT,
    cluster_params_json JSON,
    input_snapshot_path TEXT,
    input_snapshot_hash TEXT,
    code_version TEXT,
    is_stable BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS cluster_entities (
    id TEXT PRIMARY KEY,
    first_seen_run_id INTEGER NOT NULL REFERENCES cluster_runs(id),
    current_name TEXT NOT NULL,
    current_description TEXT,
    current_parent_id TEXT REFERENCES cluster_entities(id),
    status TEXT NOT NULL DEFAULT 'active',
    updated_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS cluster_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cluster_entity_id TEXT NOT NULL REFERENCES cluster_entities(id),
    cluster_run_id INTEGER NOT NULL REFERENCES cluster_runs(id),
    name TEXT NOT NULL,
    description TEXT,
    parent_cluster_entity_id TEXT REFERENCES cluster_entities(id),
    change_type TEXT NOT NULL,
    created_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS paper_cluster_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id TEXT NOT NULL REFERENCES papers(id),
    cluster_run_id INTEGER NOT NULL REFERENCES cluster_runs(id),
    cluster_version_id INTEGER NOT NULL REFERENCES cluster_versions(id),
    assignment_type TEXT NOT NULL,
    similarity_score REAL,
    assigned_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS weekly_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start DATE NOT NULL,
    week_end DATE NOT NULL,
    cluster_run_id INTEGER REFERENCES cluster_runs(id),
    analysis_run_ids_json JSON,
    input_snapshot_path TEXT,
    input_snapshot_hash TEXT,
    report_model TEXT,
    report_prompt_version TEXT,
    supersedes_report_id INTEGER REFERENCES weekly_reports(id),
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    report_content TEXT,
    highlights JSON,
    created_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id TEXT REFERENCES papers(id),
    report_id INTEGER REFERENCES weekly_reports(id),
    sync_type TEXT NOT NULL,
    logical_target TEXT NOT NULL,
    file_path TEXT NOT NULL,
    checksum TEXT NOT NULL,
    synced_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS backfill_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    range_start DATE NOT NULL,
    range_end DATE NOT NULL,
    cursor_date DATE,
    status TEXT NOT NULL DEFAULT 'pending',
    attempt_no INTEGER NOT NULL DEFAULT 0,
    worker_id TEXT,
    lease_expires_at DATETIME,
    last_error TEXT,
    cursor_semantics TEXT DEFAULT 'fixed_closed_day',
    updated_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS backfill_job_days (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backfill_job_id INTEGER NOT NULL REFERENCES backfill_jobs(id),
    work_date DATE NOT NULL,
    collect_status TEXT NOT NULL DEFAULT 'pending',
    pdf_fetch_status TEXT NOT NULL DEFAULT 'pending',
    pdf_parse_status TEXT NOT NULL DEFAULT 'pending',
    processor_status TEXT NOT NULL DEFAULT 'pending',
    analyzer_status TEXT NOT NULL DEFAULT 'pending',
    sync_status TEXT NOT NULL DEFAULT 'pending',
    is_terminal BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at DATETIME NOT NULL
);

-- Indices for common query patterns
CREATE INDEX IF NOT EXISTS idx_papers_published_date ON papers(published_date);
CREATE INDEX IF NOT EXISTS idx_papers_arxiv_id ON papers(arxiv_id);
CREATE INDEX IF NOT EXISTS idx_paper_sources_paper_id ON paper_sources(paper_id);
CREATE INDEX IF NOT EXISTS idx_paper_files_paper_id ON paper_files(paper_id);
CREATE INDEX IF NOT EXISTS idx_pdf_extractions_paper_id ON pdf_extractions(paper_id);
CREATE INDEX IF NOT EXISTS idx_stage_runs_status_stage ON stage_runs(status, stage);
CREATE INDEX IF NOT EXISTS idx_stage_runs_target ON stage_runs(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_analysis_runs_paper_id ON analysis_runs(paper_id);
CREATE INDEX IF NOT EXISTS idx_paper_analysis_analyzed_at ON paper_analysis(active_analyzed_at);
CREATE INDEX IF NOT EXISTS idx_cluster_assignments_paper ON paper_cluster_assignments(paper_id);
CREATE INDEX IF NOT EXISTS idx_cluster_assignments_run ON paper_cluster_assignments(cluster_run_id);
CREATE INDEX IF NOT EXISTS idx_sync_log_target ON sync_log(logical_target);
CREATE INDEX IF NOT EXISTS idx_backfill_job_days_job ON backfill_job_days(backfill_job_id);
```

- [ ] **Step 5: Write database.py**

`backend/core/database.py`:

```python
from __future__ import annotations

from pathlib import Path

import aiosqlite


_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class Database:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        schema = _SCHEMA_PATH.read_text()
        await self._conn.executescript(schema)

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def execute(self, sql: str, params: tuple = ()) -> int:
        assert self._conn is not None
        cursor = await self._conn.execute(sql, params)
        await self._conn.commit()
        return cursor.lastrowid or 0

    async def execute_many(self, sql: str, params_list: list[tuple]) -> None:
        assert self._conn is not None
        await self._conn.executemany(sql, params_list)
        await self._conn.commit()

    async def fetch_one(self, sql: str, params: tuple = ()) -> dict | None:
        assert self._conn is not None
        cursor = await self._conn.execute(sql, params)
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    async def fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        assert self._conn is not None
        cursor = await self._conn.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
```

- [ ] **Step 6: Run test to verify it passes**

```bash
pytest tests/backend/test_database.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/core/schema.sql backend/core/database.py tests/conftest.py tests/backend/test_database.py
git commit -m "feat: database schema (17 tables) and async SQLite connection"
```

---

## Task 4: Pydantic Models

**Files:**
- Create: `backend/core/models.py`
- Create: `tests/backend/test_models.py`

- [ ] **Step 1: Write the failing test**

`tests/backend/test_models.py`:

```python
from datetime import datetime, date

import pytest

from backend.core.models import (
    Paper,
    PaperSource,
    PaperFile,
    StageRun,
    StageStatus,
    AnalysisRun,
    PaperAnalysis,
    EmbeddingVersion,
    ClusterRun,
    WeeklyReport,
    SyncLogEntry,
)


def test_paper_creation():
    paper = Paper(
        id="2026.12345",
        title="Test Paper",
        abstract="An abstract about LLMs",
        published_date=date(2026, 4, 1),
    )
    assert paper.id == "2026.12345"
    assert paper.arxiv_id is None
    assert paper.authors is None


def test_paper_with_all_fields():
    paper = Paper(
        id="2026.12345",
        arxiv_id="2026.12345",
        title="Test Paper",
        authors=["Alice", "Bob"],
        abstract="An abstract",
        arxiv_categories=["cs.CL", "cs.AI"],
        published_date=date(2026, 4, 1),
        first_seen_at=datetime(2026, 4, 7, 10, 0, 0),
    )
    assert paper.authors == ["Alice", "Bob"]
    assert paper.arxiv_categories == ["cs.CL", "cs.AI"]


def test_paper_source_creation():
    source = PaperSource(
        paper_id="2026.12345",
        source_name="arxiv",
        source_url="https://arxiv.org/abs/2026.12345",
        match_strategy="arxiv_id",
        match_confidence=1.0,
    )
    assert source.match_strategy == "arxiv_id"
    assert source.hf_likes is None


def test_paper_file_creation():
    pf = PaperFile(
        paper_id="2026.12345",
        source_url="https://arxiv.org/pdf/2026.12345",
        sha256="abc123",
        file_size_bytes=1024000,
    )
    assert pf.file_type == "pdf"
    assert pf.is_current is False
    assert pf.download_status == "pending"


def test_stage_run_creation():
    sr = StageRun(
        target_type="paper",
        target_id="2026.12345",
        stage="pdf_fetch",
        logical_job_key="paper:2026.12345:pdf_fetch:v1",
    )
    assert sr.status == StageStatus.PENDING
    assert sr.attempt_no == 0


def test_stage_status_enum():
    assert StageStatus.PENDING == "pending"
    assert StageStatus.RUNNING == "running"
    assert StageStatus.SUCCEEDED == "succeeded"
    assert StageStatus.FAILED == "failed"
    assert StageStatus.CANCELLED == "cancelled"


def test_analysis_run_creation():
    ar = AnalysisRun(
        paper_id="2026.12345",
        analysis_basis="full_text",
        analysis_model="gpt-5.4",
        prompt_version="analysis_v1",
    )
    assert ar.analysis_basis == "full_text"
    assert ar.score_total is None
    assert ar.confidence is None


def test_paper_analysis_creation():
    pa = PaperAnalysis(
        paper_id="2026.12345",
        active_analysis_run_id=1,
        active_analyzed_at=datetime(2026, 4, 7, 12, 0, 0),
    )
    assert pa.active_paper_file_id is None


def test_embedding_version_creation():
    ev = EmbeddingVersion(
        provider="openai",
        model="text-embedding-3-small",
        dimension=1536,
        collection_name="paper_embeddings_v1",
    )
    assert ev.is_active is False


def test_weekly_report_creation():
    wr = WeeklyReport(
        week_start=date(2026, 4, 7),
        week_end=date(2026, 4, 13),
        report_content="# Weekly Report",
    )
    assert wr.is_current is True
    assert wr.supersedes_report_id is None


def test_sync_log_entry_creation():
    entry = SyncLogEntry(
        paper_id="2026.12345",
        sync_type="paper_note",
        logical_target="paper:2026.12345",
        file_path="LLM-Research/2026-W15/2026-04-07/test-paper.md",
        checksum="sha256:abc",
    )
    assert entry.report_id is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/backend/test_models.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`backend/core/models.py`:

```python
from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Paper(BaseModel):
    id: str
    arxiv_id: str | None = None
    title: str
    authors: list[str] | None = None
    abstract: str
    arxiv_categories: list[str] | None = None
    published_date: date | None = None
    first_seen_at: datetime | None = None
    updated_at: datetime | None = None


class PaperSource(BaseModel):
    id: int | None = None
    paper_id: str
    source_name: str
    source_url: str | None = None
    source_record_id: str | None = None
    match_strategy: str | None = None
    match_confidence: float | None = None
    hf_likes: int | None = None
    hf_discussions: int | None = None
    collected_at: datetime | None = None


class PaperFile(BaseModel):
    id: int | None = None
    paper_id: str
    file_type: str = "pdf"
    source_url: str | None = None
    storage_path: str | None = None
    file_size_bytes: int | None = None
    sha256: str | None = None
    mime_type: str = "application/pdf"
    is_current: bool = False
    download_status: str = "pending"
    downloaded_at: datetime | None = None
    verified_at: datetime | None = None


class PdfExtraction(BaseModel):
    id: int | None = None
    paper_id: str
    paper_file_id: int
    parser_name: str
    parser_version: str
    extraction_status: str = "pending"
    page_count: int | None = None
    extraction_root_path: str | None = None
    extracted_text_path: str | None = None
    extracted_markdown_path: str | None = None
    blocks_json_path: str | None = None
    sections_json_path: str | None = None
    figures_json_path: str | None = None
    references_json_path: str | None = None
    parse_quality_score: float | None = None
    extracted_at: datetime | None = None


class StageRun(BaseModel):
    id: int | None = None
    target_type: str
    target_id: str
    stage: str
    status: StageStatus = StageStatus.PENDING
    logical_job_key: str
    attempt_no: int = 0
    worker_id: str | None = None
    lease_expires_at: datetime | None = None
    idempotency_key: str | None = None
    payload_json: dict[str, Any] | None = None
    last_error: str | None = None
    last_error_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class StageRunAttempt(BaseModel):
    id: int | None = None
    stage_run_id: int
    attempt_no: int
    status: str = "running"
    worker_id: str
    lease_expires_at: datetime
    input_hash: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None


class AnalysisRun(BaseModel):
    id: int | None = None
    paper_id: str
    paper_file_id: int | None = None
    pdf_extraction_id: int | None = None
    chunk_manifest_path: str | None = None
    chunk_manifest_hash: str | None = None
    input_hash: str | None = None
    factual_summary: str | None = None
    methodology_inference: str | None = None
    innovation_points: list[str] | None = None
    key_takeaways: list[str] | None = None
    score_total: float | None = None
    score_breakdown: dict[str, float] | None = None
    tags: list[str] | None = None
    evidence_level: str | None = None
    analysis_basis: str = "abstract_only"
    evidence_citations: list[dict[str, Any]] | None = None
    confidence: float | None = None
    analysis_model: str | None = None
    prompt_version: str | None = None
    status: str = "pending"
    analyzed_at: datetime | None = None


class PaperAnalysis(BaseModel):
    paper_id: str
    active_analysis_run_id: int
    active_paper_file_id: int | None = None
    active_pdf_extraction_id: int | None = None
    active_analyzed_at: datetime


class EmbeddingVersion(BaseModel):
    id: int | None = None
    provider: str
    model: str
    dimension: int
    collection_name: str
    is_active: bool = False
    created_at: datetime | None = None


class ClusterRun(BaseModel):
    id: int | None = None
    run_type: str
    embedding_version_id: int
    window_start: date | None = None
    window_end: date | None = None
    paper_count: int | None = None
    algorithm_name: str = "hdbscan"
    algorithm_version: str | None = None
    cluster_params_json: dict[str, Any] | None = None
    input_snapshot_path: str | None = None
    input_snapshot_hash: str | None = None
    code_version: str | None = None
    is_stable: bool = False
    created_at: datetime | None = None


class ClusterEntity(BaseModel):
    id: str
    first_seen_run_id: int
    current_name: str
    current_description: str | None = None
    current_parent_id: str | None = None
    status: str = "active"
    updated_at: datetime | None = None


class ClusterVersion(BaseModel):
    id: int | None = None
    cluster_entity_id: str
    cluster_run_id: int
    name: str
    description: str | None = None
    parent_cluster_entity_id: str | None = None
    change_type: str
    created_at: datetime | None = None


class PaperClusterAssignment(BaseModel):
    id: int | None = None
    paper_id: str
    cluster_run_id: int
    cluster_version_id: int
    assignment_type: str
    similarity_score: float | None = None
    assigned_at: datetime | None = None


class WeeklyReport(BaseModel):
    id: int | None = None
    week_start: date
    week_end: date
    cluster_run_id: int | None = None
    analysis_run_ids_json: list[int] | None = None
    input_snapshot_path: str | None = None
    input_snapshot_hash: str | None = None
    report_model: str | None = None
    report_prompt_version: str | None = None
    supersedes_report_id: int | None = None
    is_current: bool = True
    report_content: str | None = None
    highlights: list[str] | None = None
    created_at: datetime | None = None


class SyncLogEntry(BaseModel):
    id: int | None = None
    paper_id: str | None = None
    report_id: int | None = None
    sync_type: str
    logical_target: str
    file_path: str
    checksum: str
    synced_at: datetime | None = None


class BackfillJob(BaseModel):
    id: int | None = None
    range_start: date
    range_end: date
    cursor_date: date | None = None
    status: str = "pending"
    attempt_no: int = 0
    worker_id: str | None = None
    lease_expires_at: datetime | None = None
    last_error: str | None = None
    cursor_semantics: str = "fixed_closed_day"
    updated_at: datetime | None = None


class BackfillJobDay(BaseModel):
    id: int | None = None
    backfill_job_id: int
    work_date: date
    collect_status: str = "pending"
    pdf_fetch_status: str = "pending"
    pdf_parse_status: str = "pending"
    processor_status: str = "pending"
    analyzer_status: str = "pending"
    sync_status: str = "pending"
    is_terminal: bool = False
    updated_at: datetime | None = None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/backend/test_models.py -v
```

Expected: all 12 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/core/models.py tests/backend/test_models.py
git commit -m "feat: Pydantic models for all 17 database entities"
```

---

## Task 5: Stage Runner (Lease Manager)

**Files:**
- Create: `backend/core/stage_runner.py`
- Create: `tests/backend/test_stage_runner.py`

- [ ] **Step 1: Write the failing test**

`tests/backend/test_stage_runner.py`:

```python
from datetime import datetime, timedelta

import pytest

from backend.core.database import Database
from backend.core.stage_runner import StageRunner


@pytest.fixture
async def db(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    await db.initialize()
    yield db
    await db.close()


@pytest.fixture
def runner(db):
    return StageRunner(db)


async def _insert_paper(db, paper_id="p1"):
    await db.execute(
        "INSERT INTO papers (id, title, abstract, published_date, first_seen_at, updated_at) "
        "VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))",
        (paper_id, "Test Paper", "Abstract", "2026-04-01"),
    )


async def test_create_stage_run(db, runner):
    await _insert_paper(db)
    run_id = await runner.create(
        target_type="paper",
        target_id="p1",
        stage="pdf_fetch",
    )
    assert run_id > 0
    row = await db.fetch_one("SELECT * FROM stage_runs WHERE id = ?", (run_id,))
    assert row["status"] == "pending"
    assert row["stage"] == "pdf_fetch"


async def test_create_duplicate_is_idempotent(db, runner):
    await _insert_paper(db)
    id1 = await runner.create(target_type="paper", target_id="p1", stage="pdf_fetch")
    id2 = await runner.create(target_type="paper", target_id="p1", stage="pdf_fetch")
    assert id1 == id2


async def test_claim_pending_task(db, runner):
    await _insert_paper(db)
    run_id = await runner.create(target_type="paper", target_id="p1", stage="pdf_fetch")
    claimed = await runner.claim(stage="pdf_fetch", worker_id="worker-1", lease_seconds=300)
    assert claimed is not None
    assert claimed["id"] == run_id
    assert claimed["status"] == "running"
    row = await db.fetch_one("SELECT * FROM stage_runs WHERE id = ?", (run_id,))
    assert row["status"] == "running"
    assert row["worker_id"] == "worker-1"


async def test_claim_returns_none_when_no_pending(db, runner):
    claimed = await runner.claim(stage="pdf_fetch", worker_id="worker-1", lease_seconds=300)
    assert claimed is None


async def test_claim_skips_running_tasks(db, runner):
    await _insert_paper(db)
    await runner.create(target_type="paper", target_id="p1", stage="pdf_fetch")
    await runner.claim(stage="pdf_fetch", worker_id="worker-1", lease_seconds=300)
    claimed2 = await runner.claim(stage="pdf_fetch", worker_id="worker-2", lease_seconds=300)
    assert claimed2 is None


async def test_complete_marks_succeeded(db, runner):
    await _insert_paper(db)
    run_id = await runner.create(target_type="paper", target_id="p1", stage="pdf_fetch")
    await runner.claim(stage="pdf_fetch", worker_id="worker-1", lease_seconds=300)
    await runner.complete(run_id)
    row = await db.fetch_one("SELECT * FROM stage_runs WHERE id = ?", (run_id,))
    assert row["status"] == "succeeded"


async def test_fail_marks_failed_with_error(db, runner):
    await _insert_paper(db)
    run_id = await runner.create(target_type="paper", target_id="p1", stage="pdf_fetch")
    await runner.claim(stage="pdf_fetch", worker_id="worker-1", lease_seconds=300)
    await runner.fail(run_id, error="Connection timeout")
    row = await db.fetch_one("SELECT * FROM stage_runs WHERE id = ?", (run_id,))
    assert row["status"] == "failed"
    assert row["last_error"] == "Connection timeout"


async def test_retry_creates_new_attempt(db, runner):
    await _insert_paper(db)
    run_id = await runner.create(target_type="paper", target_id="p1", stage="pdf_fetch")
    await runner.claim(stage="pdf_fetch", worker_id="worker-1", lease_seconds=300)
    await runner.fail(run_id, error="timeout")

    await runner.retry(run_id)
    row = await db.fetch_one("SELECT * FROM stage_runs WHERE id = ?", (run_id,))
    assert row["status"] == "pending"
    assert row["attempt_no"] == 1

    attempts = await db.fetch_all(
        "SELECT * FROM stage_run_attempts WHERE stage_run_id = ?", (run_id,)
    )
    assert len(attempts) == 1
    assert attempts[0]["status"] == "failed"


async def test_reclaim_expired_lease(db, runner):
    await _insert_paper(db)
    run_id = await runner.create(target_type="paper", target_id="p1", stage="pdf_fetch")
    await runner.claim(stage="pdf_fetch", worker_id="worker-1", lease_seconds=1)

    # Simulate expired lease by backdating
    await db.execute(
        "UPDATE stage_runs SET lease_expires_at = datetime('now', '-10 seconds') WHERE id = ?",
        (run_id,),
    )
    reclaimed = await runner.reclaim_expired(stage="pdf_fetch", worker_id="worker-2", lease_seconds=300)
    assert reclaimed is not None
    assert reclaimed["worker_id"] == "worker-2"


async def test_list_by_status(db, runner):
    await _insert_paper(db, "p1")
    await _insert_paper(db, "p2")
    await runner.create(target_type="paper", target_id="p1", stage="pdf_fetch")
    await runner.create(target_type="paper", target_id="p2", stage="pdf_fetch")

    pending = await runner.list_by_status(stage="pdf_fetch", status="pending")
    assert len(pending) == 2
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/backend/test_stage_runner.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`backend/core/stage_runner.py`:

```python
from __future__ import annotations

from backend.core.database import Database


class StageRunner:
    def __init__(self, db: Database):
        self._db = db

    async def create(
        self,
        target_type: str,
        target_id: str,
        stage: str,
        payload: dict | None = None,
    ) -> int:
        logical_job_key = f"{target_type}:{target_id}:{stage}"

        existing = await self._db.fetch_one(
            "SELECT id FROM stage_runs WHERE logical_job_key = ? AND status NOT IN ('cancelled')",
            (logical_job_key,),
        )
        if existing:
            return existing["id"]

        run_id = await self._db.execute(
            "INSERT INTO stage_runs "
            "(target_type, target_id, stage, status, logical_job_key, attempt_no, "
            " payload_json, created_at, updated_at) "
            "VALUES (?, ?, ?, 'pending', ?, 0, ?, datetime('now'), datetime('now'))",
            (target_type, target_id, stage, logical_job_key, str(payload) if payload else None),
        )
        return run_id

    async def claim(
        self,
        stage: str,
        worker_id: str,
        lease_seconds: int = 300,
    ) -> dict | None:
        row = await self._db.fetch_one(
            "SELECT id FROM stage_runs WHERE stage = ? AND status = 'pending' ORDER BY created_at LIMIT 1",
            (stage,),
        )
        if not row:
            return None

        run_id = row["id"]
        await self._db.execute(
            "UPDATE stage_runs SET status = 'running', worker_id = ?, "
            "lease_expires_at = datetime('now', '+' || ? || ' seconds'), "
            "updated_at = datetime('now') "
            "WHERE id = ? AND status = 'pending'",
            (worker_id, str(lease_seconds), run_id),
        )

        # Record the attempt
        current = await self._db.fetch_one("SELECT * FROM stage_runs WHERE id = ?", (run_id,))
        await self._db.execute(
            "INSERT INTO stage_run_attempts "
            "(stage_run_id, attempt_no, status, worker_id, lease_expires_at, started_at) "
            "VALUES (?, ?, 'running', ?, ?, datetime('now'))",
            (run_id, current["attempt_no"], worker_id, current["lease_expires_at"]),
        )

        return dict(current)

    async def complete(self, run_id: int) -> None:
        current = await self._db.fetch_one("SELECT attempt_no FROM stage_runs WHERE id = ?", (run_id,))
        await self._db.execute(
            "UPDATE stage_runs SET status = 'succeeded', updated_at = datetime('now') WHERE id = ?",
            (run_id,),
        )
        if current:
            await self._db.execute(
                "UPDATE stage_run_attempts SET status = 'succeeded', finished_at = datetime('now') "
                "WHERE stage_run_id = ? AND attempt_no = ?",
                (run_id, current["attempt_no"]),
            )

    async def fail(self, run_id: int, error: str) -> None:
        current = await self._db.fetch_one("SELECT attempt_no FROM stage_runs WHERE id = ?", (run_id,))
        await self._db.execute(
            "UPDATE stage_runs SET status = 'failed', last_error = ?, last_error_at = datetime('now'), "
            "updated_at = datetime('now') WHERE id = ?",
            (error, run_id),
        )
        if current:
            await self._db.execute(
                "UPDATE stage_run_attempts SET status = 'failed', finished_at = datetime('now'), "
                "error_message = ? WHERE stage_run_id = ? AND attempt_no = ?",
                (error, run_id, current["attempt_no"]),
            )

    async def retry(self, run_id: int) -> None:
        await self._db.execute(
            "UPDATE stage_runs SET status = 'pending', attempt_no = attempt_no + 1, "
            "worker_id = NULL, lease_expires_at = NULL, updated_at = datetime('now') WHERE id = ?",
            (run_id,),
        )

    async def reclaim_expired(
        self,
        stage: str,
        worker_id: str,
        lease_seconds: int = 300,
    ) -> dict | None:
        row = await self._db.fetch_one(
            "SELECT id FROM stage_runs "
            "WHERE stage = ? AND status = 'running' AND lease_expires_at < datetime('now') "
            "ORDER BY lease_expires_at LIMIT 1",
            (stage,),
        )
        if not row:
            return None

        run_id = row["id"]

        # Fail the old attempt
        current = await self._db.fetch_one("SELECT attempt_no FROM stage_runs WHERE id = ?", (run_id,))
        if current:
            await self._db.execute(
                "UPDATE stage_run_attempts SET status = 'failed', finished_at = datetime('now'), "
                "error_message = 'lease expired' WHERE stage_run_id = ? AND attempt_no = ?",
                (run_id, current["attempt_no"]),
            )

        # Increment attempt and reclaim
        await self._db.execute(
            "UPDATE stage_runs SET status = 'running', worker_id = ?, attempt_no = attempt_no + 1, "
            "lease_expires_at = datetime('now', '+' || ? || ' seconds'), "
            "updated_at = datetime('now') WHERE id = ?",
            (worker_id, str(lease_seconds), run_id),
        )

        updated = await self._db.fetch_one("SELECT * FROM stage_runs WHERE id = ?", (run_id,))

        # Record new attempt
        await self._db.execute(
            "INSERT INTO stage_run_attempts "
            "(stage_run_id, attempt_no, status, worker_id, lease_expires_at, started_at) "
            "VALUES (?, ?, 'running', ?, ?, datetime('now'))",
            (run_id, updated["attempt_no"], worker_id, updated["lease_expires_at"]),
        )

        return dict(updated)

    async def list_by_status(
        self,
        stage: str,
        status: str,
        limit: int = 100,
    ) -> list[dict]:
        return await self._db.fetch_all(
            "SELECT * FROM stage_runs WHERE stage = ? AND status = ? ORDER BY created_at LIMIT ?",
            (stage, status, limit),
        )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/backend/test_stage_runner.py -v
```

Expected: all 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/core/stage_runner.py tests/backend/test_stage_runner.py
git commit -m "feat: stage runner with lease-based task claiming and retry"
```

---

## Task 6: LLM Client

**Files:**
- Create: `backend/core/llm_client.py`
- Create: `tests/backend/test_llm_client.py`

- [ ] **Step 1: Write the failing test**

`tests/backend/test_llm_client.py`:

```python
import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from backend.core.llm_client import LLMClient


@pytest.fixture
def client():
    return LLMClient(
        base_url="https://api.openai.com/v1",
        api_key="sk-test",
        model="gpt-5.4",
    )


def test_client_initialization(client):
    assert client.model == "gpt-5.4"


async def test_chat_returns_string(client):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Hello, world!"

    with patch.object(client._client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        result = await client.chat([{"role": "user", "content": "Hi"}])
        assert result == "Hello, world!"
        mock_create.assert_called_once()


async def test_chat_passes_model_and_messages(client):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "response"

    with patch.object(client._client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        messages = [{"role": "user", "content": "test"}]
        await client.chat(messages, temperature=0.1)
        call_kwargs = mock_create.call_args
        assert call_kwargs.kwargs["model"] == "gpt-5.4"
        assert call_kwargs.kwargs["messages"] == messages
        assert call_kwargs.kwargs["temperature"] == 0.1


async def test_chat_json_returns_parsed_dict(client):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"score": 8.5, "tags": ["ml", "nlp"]}'

    with patch.object(client._client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        schema = {"type": "object", "properties": {"score": {"type": "number"}}}
        result = await client.chat_json(
            [{"role": "user", "content": "analyze"}],
            response_schema=schema,
        )
        assert result == {"score": 8.5, "tags": ["ml", "nlp"]}


async def test_chat_json_raises_on_invalid_json(client):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "not json"

    with patch.object(client._client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        with pytest.raises(ValueError, match="Failed to parse LLM response as JSON"):
            await client.chat_json(
                [{"role": "user", "content": "analyze"}],
                response_schema={},
            )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/backend/test_llm_client.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`backend/core/llm_client.py`:

```python
from __future__ import annotations

import json

from openai import AsyncOpenAI


class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.model = model
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    async def chat(self, messages: list[dict], **kwargs) -> str:
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs,
        )
        return response.choices[0].message.content

    async def chat_json(
        self,
        messages: list[dict],
        response_schema: dict,
        **kwargs,
    ) -> dict:
        kwargs.setdefault("response_format", {"type": "json_object"})
        raw = await self.chat(messages, **kwargs)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse LLM response as JSON: {e}") from e
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/backend/test_llm_client.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/core/llm_client.py tests/backend/test_llm_client.py
git commit -m "feat: LLM client with OpenAI protocol, chat and chat_json methods"
```

---

## Task 7: Embedding Client

**Files:**
- Create: `backend/core/embedding_client.py`
- Create: `tests/backend/test_embedding_client.py`

- [ ] **Step 1: Write the failing test**

`tests/backend/test_embedding_client.py`:

```python
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from backend.core.embedding_client import EmbeddingClient


@pytest.fixture
def client():
    return EmbeddingClient(
        base_url="https://api.openai.com/v1",
        api_key="sk-test",
        model="text-embedding-3-small",
    )


def test_client_initialization(client):
    assert client.model == "text-embedding-3-small"


async def test_embed_single_text(client):
    mock_embedding = MagicMock()
    mock_embedding.embedding = [0.1, 0.2, 0.3]
    mock_response = MagicMock()
    mock_response.data = [mock_embedding]

    with patch.object(client._client.embeddings, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        result = await client.embed(["hello world"])
        assert result == [[0.1, 0.2, 0.3]]
        mock_create.assert_called_once_with(
            model="text-embedding-3-small",
            input=["hello world"],
        )


async def test_embed_multiple_texts(client):
    mock_emb1 = MagicMock()
    mock_emb1.embedding = [0.1, 0.2]
    mock_emb2 = MagicMock()
    mock_emb2.embedding = [0.3, 0.4]
    mock_response = MagicMock()
    mock_response.data = [mock_emb1, mock_emb2]

    with patch.object(client._client.embeddings, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        result = await client.embed(["text one", "text two"])
        assert len(result) == 2
        assert result[0] == [0.1, 0.2]
        assert result[1] == [0.3, 0.4]


async def test_embed_empty_list(client):
    result = await client.embed([])
    assert result == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/backend/test_embedding_client.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`backend/core/embedding_client.py`:

```python
from __future__ import annotations

from openai import AsyncOpenAI


class EmbeddingClient:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.model = model
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = await self._client.embeddings.create(
            model=self.model,
            input=texts,
        )
        return [item.embedding for item in response.data]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/backend/test_embedding_client.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/core/embedding_client.py tests/backend/test_embedding_client.py
git commit -m "feat: embedding client with OpenAI protocol, model-agnostic"
```

---

## Task 8: ChromaDB Vector Store

**Files:**
- Create: `backend/core/vector_store.py`
- Create: `tests/backend/test_vector_store.py`

- [ ] **Step 1: Write the failing test**

`tests/backend/test_vector_store.py`:

```python
import pytest

from backend.core.vector_store import VectorStore


@pytest.fixture
def store(tmp_path):
    return VectorStore(persist_dir=str(tmp_path / "chroma"))


def test_store_initialization(store):
    assert store is not None


def test_get_or_create_collection(store):
    collection = store.get_or_create_collection("paper_embeddings_v1")
    assert collection is not None
    assert collection.name == "paper_embeddings_v1"


def test_add_embeddings(store):
    collection = store.get_or_create_collection("test_collection")
    store.add(
        collection_name="test_collection",
        ids=["p1", "p2"],
        embeddings=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
        metadatas=[
            {"paper_id": "p1", "analysis_basis": "full_text"},
            {"paper_id": "p2", "analysis_basis": "abstract_only"},
        ],
    )
    result = store.get("test_collection", ids=["p1"])
    assert len(result["ids"]) == 1
    assert result["ids"][0] == "p1"


def test_query_returns_nearest(store):
    store.get_or_create_collection("test_collection")
    store.add(
        collection_name="test_collection",
        ids=["p1", "p2", "p3"],
        embeddings=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.9, 0.1, 0.0]],
        metadatas=[
            {"paper_id": "p1"},
            {"paper_id": "p2"},
            {"paper_id": "p3"},
        ],
    )
    results = store.query(
        collection_name="test_collection",
        query_embeddings=[[1.0, 0.0, 0.0]],
        n_results=2,
    )
    assert len(results["ids"][0]) == 2
    assert "p1" in results["ids"][0]


def test_upsert_overwrites_existing(store):
    store.get_or_create_collection("test_collection")
    store.add(
        collection_name="test_collection",
        ids=["p1"],
        embeddings=[[0.1, 0.2, 0.3]],
        metadatas=[{"paper_id": "p1", "version": "old"}],
    )
    store.upsert(
        collection_name="test_collection",
        ids=["p1"],
        embeddings=[[0.4, 0.5, 0.6]],
        metadatas=[{"paper_id": "p1", "version": "new"}],
    )
    result = store.get("test_collection", ids=["p1"])
    assert result["metadatas"][0]["version"] == "new"


def test_delete_embeddings(store):
    store.get_or_create_collection("test_collection")
    store.add(
        collection_name="test_collection",
        ids=["p1", "p2"],
        embeddings=[[0.1, 0.2], [0.3, 0.4]],
        metadatas=[{"paper_id": "p1"}, {"paper_id": "p2"}],
    )
    store.delete("test_collection", ids=["p1"])
    result = store.get("test_collection", ids=["p1"])
    assert len(result["ids"]) == 0


def test_count(store):
    store.get_or_create_collection("test_collection")
    store.add(
        collection_name="test_collection",
        ids=["p1", "p2", "p3"],
        embeddings=[[0.1], [0.2], [0.3]],
        metadatas=[{"paper_id": "p1"}, {"paper_id": "p2"}, {"paper_id": "p3"}],
    )
    assert store.count("test_collection") == 3


def test_list_collections(store):
    store.get_or_create_collection("collection_a")
    store.get_or_create_collection("collection_b")
    names = store.list_collections()
    assert "collection_a" in names
    assert "collection_b" in names
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/backend/test_vector_store.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`backend/core/vector_store.py`:

```python
from __future__ import annotations

from typing import Any

import chromadb


class VectorStore:
    def __init__(self, persist_dir: str):
        self._client = chromadb.PersistentClient(path=persist_dir)

    def get_or_create_collection(self, name: str) -> chromadb.Collection:
        return self._client.get_or_create_collection(name=name)

    def add(
        self,
        collection_name: str,
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        collection = self._client.get_collection(collection_name)
        collection.add(ids=ids, embeddings=embeddings, metadatas=metadatas)

    def upsert(
        self,
        collection_name: str,
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        collection = self._client.get_collection(collection_name)
        collection.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas)

    def get(
        self,
        collection_name: str,
        ids: list[str] | None = None,
        where: dict | None = None,
    ) -> dict:
        collection = self._client.get_collection(collection_name)
        kwargs = {}
        if ids:
            kwargs["ids"] = ids
        if where:
            kwargs["where"] = where
        return collection.get(**kwargs)

    def query(
        self,
        collection_name: str,
        query_embeddings: list[list[float]],
        n_results: int = 10,
        where: dict | None = None,
    ) -> dict:
        collection = self._client.get_collection(collection_name)
        kwargs: dict[str, Any] = {
            "query_embeddings": query_embeddings,
            "n_results": n_results,
        }
        if where:
            kwargs["where"] = where
        return collection.query(**kwargs)

    def delete(
        self,
        collection_name: str,
        ids: list[str],
    ) -> None:
        collection = self._client.get_collection(collection_name)
        collection.delete(ids=ids)

    def count(self, collection_name: str) -> int:
        collection = self._client.get_collection(collection_name)
        return collection.count()

    def list_collections(self) -> list[str]:
        collections = self._client.list_collections()
        return [c.name for c in collections]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/backend/test_vector_store.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/core/vector_store.py tests/backend/test_vector_store.py
git commit -m "feat: ChromaDB vector store with versioned collections"
```

---

## Task 9: Minimal FastAPI Entry Point

**Files:**
- Create: `backend/main.py`
- Create: `tests/backend/test_main.py`

- [ ] **Step 1: Write the failing test**

`tests/backend/test_main.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_health_endpoint(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/backend/test_main.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`backend/main.py`:

```python
from fastapi import FastAPI

app = FastAPI(title="LLM Paper Tracker", version="0.1.0")


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/backend/test_main.py -v
```

Expected: 1 test PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py tests/backend/test_main.py
git commit -m "feat: minimal FastAPI app with health endpoint"
```

---

## Task 10: Run Full Test Suite and Final Verification

- [ ] **Step 1: Run all tests**

```bash
pytest tests/ -v --tb=short
```

Expected: all tests PASS (approximately 46 tests across 8 test files).

- [ ] **Step 2: Run ruff lint check**

```bash
ruff check backend/ tests/
```

Expected: no errors.

- [ ] **Step 3: Verify the project runs**

```bash
OPENAI_API_KEY=sk-placeholder uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
sleep 2
curl http://localhost:8000/api/health
kill %1
```

Expected: `{"status":"ok","version":"0.1.0"}`

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore: plan 1 complete — core foundation verified"
```

---

## What Plan 1 Delivers

After completing all tasks, you have:

| Component | Status |
|-----------|--------|
| Project scaffolding (pyproject.toml, dirs) | Done |
| YAML config with env var interpolation | Done |
| SQLite database with 17 tables + indices | Done |
| Pydantic models for all entities | Done |
| Stage runner with lease-based task claiming, retry, reclaim | Done |
| LLM Client (OpenAI protocol, model-agnostic) | Done |
| Embedding Client (OpenAI protocol, swappable) | Done |
| ChromaDB vector store with versioned collections | Done |
| FastAPI health endpoint | Done |
| Full test coverage for all above | Done |

## Next Plans

- **Plan 2: Data Collection** — arXiv + HuggingFace collectors
- **Plan 3: PDF Pipeline** — PDF Fetcher + Parser + storage
- **Plan 4: Processor** — clean, normalize, chunk, dedup
- **Plan 5: Analyzer** — LLM deep reading, scoring, tagging, provisional clustering
- **Plan 6: Obsidian Sync** — Note generation, daily summary, file sync
- **Plan 7: Reporter** — stable clustering, weekly reports
- **Plan 8: API Server** — all REST endpoints
- **Plan 9: Scheduler + Backfiller** — cron jobs, historical backfill
- **Plan 10: Frontend** — React Web UI
