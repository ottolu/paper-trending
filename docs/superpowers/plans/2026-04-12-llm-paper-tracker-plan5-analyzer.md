# Analyzer (Plan 5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Analyzer service that claims `analyzer` stage_runs, reads the chunk manifest, calls the LLM for structured analysis (summary, methodology, scores, tags, citations), writes `analysis_runs` + `paper_analysis` projection, generates embeddings, and creates `sync` stage_runs.

**Architecture:** `AnalyzerService` claims tasks, reads the manifest JSON, calls `LLMClient.chat_json()` with a structured prompt, writes the result to `analysis_runs`, updates `paper_analysis` active projection, calls `EmbeddingClient.embed()` + `VectorStore.upsert()`, and creates the `sync` stage_run. Provisional clustering is deferred to Plan 7 (Reporter).

**Tech Stack:** existing LLMClient, EmbeddingClient, VectorStore, Database, StageRunner from Plan 1.

---

## File Structure

| File | Responsibility |
|------|---------------|
| `backend/analyzer/__init__.py` | Package init |
| `backend/analyzer/prompts.py` | Prompt templates for LLM analysis |
| `backend/analyzer/service.py` | `AnalyzerService` — orchestrate LLM analysis, write results, embed, create sync task |
| `tests/backend/test_analyzer/__init__.py` | Test package init |
| `tests/backend/test_analyzer/test_prompts.py` | Tests for prompt assembly |
| `tests/backend/test_analyzer/test_service.py` | Tests for AnalyzerService |

---

### Task 1: Analysis Prompts

**Files:**
- Create: `backend/analyzer/__init__.py`
- Create: `backend/analyzer/prompts.py`
- Create: `tests/backend/test_analyzer/__init__.py`
- Create: `tests/backend/test_analyzer/test_prompts.py`

- [ ] **Step 1: Write the failing tests**

```python
from backend.analyzer.prompts import build_analysis_prompt


def test_build_prompt_with_full_text():
    manifest = {
        "paper_id": "2401.00001",
        "title": "Test Paper",
        "abstract": "This is the abstract.",
        "authors": ["Author A"],
        "arxiv_categories": ["cs.CL"],
        "analysis_basis": "full_text",
        "chunks": [
            {"text": "Introduction text.", "index": 0, "char_count": 18},
            {"text": "Methods text.", "index": 1, "char_count": 13},
        ],
        "sections": [{"title": "Introduction", "level": 1}],
    }
    messages = build_analysis_prompt(manifest)

    assert len(messages) >= 2
    assert messages[0]["role"] == "system"
    assert "JSON" in messages[0]["content"]
    user_msg = messages[-1]["content"]
    assert "Test Paper" in user_msg
    assert "This is the abstract." in user_msg
    assert "Introduction text." in user_msg


def test_build_prompt_abstract_only():
    manifest = {
        "paper_id": "2401.00002",
        "title": "Abstract Only Paper",
        "abstract": "Only abstract available.",
        "authors": ["Author B"],
        "arxiv_categories": ["cs.AI"],
        "analysis_basis": "abstract_only",
        "chunks": [],
        "sections": [],
    }
    messages = build_analysis_prompt(manifest)
    user_msg = messages[-1]["content"]
    assert "Only abstract available." in user_msg
    assert "abstract_only" in user_msg.lower() or "abstract only" in user_msg.lower()


def test_prompt_requests_required_fields():
    manifest = {
        "paper_id": "2401.00001",
        "title": "T",
        "abstract": "A",
        "authors": [],
        "arxiv_categories": [],
        "analysis_basis": "abstract_only",
        "chunks": [],
        "sections": [],
    }
    messages = build_analysis_prompt(manifest)
    system_msg = messages[0]["content"]
    for field in ["factual_summary", "methodology_inference", "innovation_points",
                   "key_takeaways", "score_total", "tags"]:
        assert field in system_msg
```

- [ ] **Step 2: Write the implementation**

```python
from __future__ import annotations

ANALYSIS_SYSTEM_PROMPT = """You are an expert AI research paper analyst. Analyze the given paper and produce a structured JSON response.

Required JSON fields:
- factual_summary: string — objective summary of what the paper does and finds
- methodology_inference: string — what methods/techniques are used
- innovation_points: list[string] — key novel contributions
- key_takeaways: list[string] — most important points for a researcher
- score_total: float (0-10) — overall significance score
- score_breakdown: object with keys "novelty", "rigor", "impact", "clarity" (each 0-10)
- tags: list[string] — topic tags for categorization
- evidence_level: string — "strong", "moderate", or "limited"
- evidence_citations: list[object] — each with "claim", "source", "page" (if available)
- confidence: float (0-1) — your confidence in this analysis

Output ONLY valid JSON, no markdown fences or explanation."""


def build_analysis_prompt(manifest: dict) -> list[dict]:
    title = manifest["title"]
    abstract = manifest["abstract"]
    authors = ", ".join(manifest.get("authors", []))
    categories = ", ".join(manifest.get("arxiv_categories", []))
    analysis_basis = manifest.get("analysis_basis", "abstract_only")
    chunks = manifest.get("chunks", [])
    sections = manifest.get("sections", [])

    user_parts = [
        f"# Paper: {title}",
        f"Authors: {authors}",
        f"Categories: {categories}",
        f"Analysis basis: {analysis_basis}",
        f"\n## Abstract\n{abstract}",
    ]

    if chunks:
        user_parts.append("\n## Full Text Chunks")
        for chunk in chunks:
            text = chunk["text"] if isinstance(chunk, dict) else chunk
            idx = chunk.get("index", "?") if isinstance(chunk, dict) else "?"
            user_parts.append(f"\n### Chunk {idx}\n{text}")

    if sections:
        section_names = [s.get("title", "") for s in sections if isinstance(s, dict)]
        if section_names:
            user_parts.append(f"\n## Document Sections: {', '.join(section_names)}")

    if analysis_basis == "abstract_only":
        user_parts.append(
            "\nNote: Only abstract is available (abstract_only). "
            "Base analysis solely on abstract. Set confidence accordingly."
        )

    return [
        {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(user_parts)},
    ]
```

- [ ] **Step 3: Run tests, lint, commit**

```bash
pytest tests/backend/test_analyzer/test_prompts.py -v
ruff check backend/analyzer/ tests/backend/test_analyzer/
git commit -m "feat: analysis prompt templates for LLM paper reading"
```

---

### Task 2: AnalyzerService

**Files:**
- Create: `backend/analyzer/service.py`
- Create: `tests/backend/test_analyzer/test_service.py`

- [ ] **Step 1: Write the failing tests**

```python
import ast
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.analyzer.service import AnalyzerService
from backend.core.database import Database
from backend.core.stage_runner import StageRunner


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
def mock_llm():
    client = AsyncMock()
    client.chat_json = AsyncMock(return_value={
        "factual_summary": "This paper studies scaling laws.",
        "methodology_inference": "Empirical evaluation across model sizes.",
        "innovation_points": ["New scaling predictions"],
        "key_takeaways": ["Bigger models are more efficient"],
        "score_total": 8.5,
        "score_breakdown": {"novelty": 8, "rigor": 9, "impact": 9, "clarity": 8},
        "tags": ["scaling-laws", "language-models"],
        "evidence_level": "strong",
        "evidence_citations": [{"claim": "scaling follows power law", "source": "full_text", "page": 3}],
        "confidence": 0.85,
    })
    return client


@pytest.fixture
def mock_embedding():
    client = AsyncMock()
    client.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
    return client


@pytest.fixture
def mock_vector_store():
    store = MagicMock()
    store.get_or_create_collection = MagicMock()
    store.upsert = MagicMock()
    return store


@pytest.fixture
def service(db, stage_runner, data_root, mock_llm, mock_embedding, mock_vector_store):
    return AnalyzerService(
        db=db,
        stage_runner=stage_runner,
        paper_root=data_root,
        llm_client=mock_llm,
        embedding_client=mock_embedding,
        vector_store=mock_vector_store,
        embedding_version_id=1,
        embedding_collection="paper_embeddings_v1",
    )


async def _setup_paper_with_manifest(db, data_root, paper_id="paper-001"):
    await db.execute(
        "INSERT INTO papers (id, title, abstract, authors, arxiv_categories, first_seen_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))",
        (paper_id, "Test Paper", "Abstract text.", '["Author A"]', '["cs.CL"]'),
    )
    manifest = {
        "paper_id": paper_id,
        "title": "Test Paper",
        "abstract": "Abstract text.",
        "authors": ["Author A"],
        "arxiv_categories": ["cs.CL"],
        "analysis_basis": "full_text",
        "chunks": [{"text": "Chunk one.", "index": 0, "char_count": 10}],
        "sections": [],
    }
    cache_dir = Path(data_root) / paper_id / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = cache_dir / "abc123.json"
    manifest_path.write_text(json.dumps(manifest))

    await db.execute(
        "INSERT INTO stage_runs (target_type, target_id, stage, status, logical_job_key, "
        "attempt_no, payload_json, created_at, updated_at) "
        "VALUES ('paper', ?, 'analyzer', 'pending', ?, 0, ?, datetime('now'), datetime('now'))",
        (paper_id, f"paper:{paper_id}:analyzer",
         str({"chunk_manifest_path": str(manifest_path), "chunk_manifest_hash": "abc123", "analysis_basis": "full_text"})),
    )
    return str(manifest_path)


async def test_process_writes_analysis_run(service, db, data_root):
    await _setup_paper_with_manifest(db, data_root)

    await service.process_next()

    row = await db.fetch_one("SELECT * FROM analysis_runs WHERE paper_id = ?", ("paper-001",))
    assert row is not None
    assert row["factual_summary"] == "This paper studies scaling laws."
    assert row["score_total"] == 8.5
    assert row["status"] == "succeeded"
    assert row["analysis_basis"] == "full_text"


async def test_process_updates_paper_analysis_projection(service, db, data_root):
    await _setup_paper_with_manifest(db, data_root)

    await service.process_next()

    projection = await db.fetch_one("SELECT * FROM paper_analysis WHERE paper_id = ?", ("paper-001",))
    assert projection is not None
    assert projection["active_analysis_run_id"] is not None


async def test_process_calls_embedding(service, db, data_root, mock_embedding, mock_vector_store):
    await _setup_paper_with_manifest(db, data_root)

    await service.process_next()

    mock_embedding.embed.assert_called_once()
    mock_vector_store.upsert.assert_called_once()


async def test_process_creates_sync_stage_run(service, db, stage_runner, data_root):
    await _setup_paper_with_manifest(db, data_root)

    await service.process_next()

    sync_runs = await stage_runner.list_by_status("sync", "pending")
    assert len(sync_runs) == 1
    assert sync_runs[0]["target_id"] == "paper-001"


async def test_process_next_returns_false_when_no_tasks(service):
    result = await service.process_next()
    assert result is False
```

- [ ] **Step 2: Write the implementation**

```python
from __future__ import annotations

import ast
import json
import logging
from pathlib import Path

from backend.analyzer.prompts import build_analysis_prompt
from backend.core.database import Database
from backend.core.stage_runner import StageRunner

logger = logging.getLogger(__name__)


class AnalyzerService:
    def __init__(
        self,
        db: Database,
        stage_runner: StageRunner,
        paper_root: str,
        llm_client,
        embedding_client,
        vector_store,
        embedding_version_id: int = 1,
        embedding_collection: str = "paper_embeddings_v1",
    ):
        self._db = db
        self._stage_runner = stage_runner
        self._paper_root = Path(paper_root)
        self._llm = llm_client
        self._embedding = embedding_client
        self._vector_store = vector_store
        self._embedding_version_id = embedding_version_id
        self._embedding_collection = embedding_collection

    async def process_next(self, worker_id: str = "analyzer-1") -> bool:
        task = await self._stage_runner.claim("analyzer", worker_id)
        if not task:
            return False

        try:
            payload_str = task["payload_json"]
            if payload_str:
                try:
                    payload = json.loads(payload_str)
                except (json.JSONDecodeError, TypeError):
                    payload = ast.literal_eval(payload_str)
            else:
                payload = {}

            paper_id = task["target_id"]
            manifest_path = payload.get("chunk_manifest_path", "")
            analysis_basis = payload.get("analysis_basis", "abstract_only")

            manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
            messages = build_analysis_prompt(manifest)
            analysis = await self._llm.chat_json(messages)

            analysis_run_id = await self._db.execute(
                "INSERT INTO analysis_runs (paper_id, chunk_manifest_path, chunk_manifest_hash, "
                "input_hash, factual_summary, methodology_inference, innovation_points, "
                "key_takeaways, score_total, score_breakdown, tags, evidence_level, "
                "analysis_basis, evidence_citations, confidence, status, analyzed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'succeeded', datetime('now'))",
                (
                    paper_id,
                    manifest_path,
                    payload.get("chunk_manifest_hash"),
                    None,
                    analysis.get("factual_summary", ""),
                    analysis.get("methodology_inference", ""),
                    json.dumps(analysis.get("innovation_points", [])),
                    json.dumps(analysis.get("key_takeaways", [])),
                    analysis.get("score_total", 0),
                    json.dumps(analysis.get("score_breakdown", {})),
                    json.dumps(analysis.get("tags", [])),
                    analysis.get("evidence_level", "limited"),
                    analysis_basis,
                    json.dumps(analysis.get("evidence_citations", [])),
                    analysis.get("confidence", 0),
                ),
            )

            existing = await self._db.fetch_one(
                "SELECT paper_id FROM paper_analysis WHERE paper_id = ?", (paper_id,)
            )
            if existing:
                await self._db.execute(
                    "UPDATE paper_analysis SET active_analysis_run_id = ?, "
                    "active_analyzed_at = datetime('now') WHERE paper_id = ?",
                    (analysis_run_id, paper_id),
                )
            else:
                await self._db.execute(
                    "INSERT INTO paper_analysis (paper_id, active_analysis_run_id, active_analyzed_at) "
                    "VALUES (?, ?, datetime('now'))",
                    (paper_id, analysis_run_id),
                )

            embed_text = f"{manifest['title']}\n{manifest['abstract']}"
            embeddings = await self._embedding.embed([embed_text])
            if embeddings:
                self._vector_store.get_or_create_collection(self._embedding_collection)
                self._vector_store.upsert(
                    collection_name=self._embedding_collection,
                    ids=[paper_id],
                    embeddings=embeddings,
                    metadatas=[{
                        "paper_id": paper_id,
                        "analysis_basis": analysis_basis,
                        "embedding_version_id": self._embedding_version_id,
                    }],
                )

            await self._stage_runner.complete(task["id"])
            await self._stage_runner.create(
                target_type="paper",
                target_id=paper_id,
                stage="sync",
            )
            return True
        except Exception as e:
            await self._stage_runner.fail(task["id"], str(e))
            return True
```

- [ ] **Step 3: Run tests, lint, commit**

```bash
pytest tests/backend/test_analyzer/test_service.py -v
ruff check backend/analyzer/ tests/backend/test_analyzer/
git commit -m "feat: analyzer service with LLM analysis, embedding, and sync task creation"
```

---

### Task 3: Full Test Suite Verification

- [ ] **Step 1: Run all tests**

Run: `pytest tests/ -v`
Expected: All pass (~111 total)

- [ ] **Step 2: Run linter**

Run: `ruff check .`
Expected: All checks passed
