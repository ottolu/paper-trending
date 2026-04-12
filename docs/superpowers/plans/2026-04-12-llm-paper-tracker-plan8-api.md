# API Server (Plan 8) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI REST API endpoints for papers (list/detail), reports (list/detail), semantic search, and job triggers (collect, retry). All list endpoints use unified pagination. Existing `backend/main.py` already has the FastAPI app and health endpoint.

**Architecture:** Route modules in `backend/api/` with a router per domain. Each router uses the Database directly for reads. The app factory in `main.py` includes all routers. Tests use `httpx.AsyncClient` with FastAPI's `ASGITransport`.

**Tech Stack:** FastAPI, httpx (test client), existing Database from Plan 1.

---

## File Structure

| File | Responsibility |
|------|---------------|
| `backend/api/__init__.py` | Package init |
| `backend/api/papers.py` | `/api/papers` and `/api/papers/{paper_id}` routes |
| `backend/api/reports.py` | `/api/reports` and `/api/reports/{report_id}` routes |
| `backend/api/search.py` | `/api/search/semantic` route |
| `backend/api/jobs.py` | `/api/jobs/collect`, `/api/stages/retry` routes |
| `backend/api/deps.py` | Dependency injection: get_db, get_stage_runner, etc. |
| `backend/main.py` | Modified: include routers |
| `tests/backend/test_api/__init__.py` | Test package init |
| `tests/backend/test_api/test_papers.py` | Tests for papers endpoints |
| `tests/backend/test_api/test_reports.py` | Tests for reports endpoints |
| `tests/backend/test_api/test_search.py` | Tests for semantic search |
| `tests/backend/test_api/test_jobs.py` | Tests for job trigger endpoints |

---

### Task 1: Dependencies and Papers API

**Files:**
- Create: `backend/api/__init__.py`
- Create: `backend/api/deps.py`
- Create: `backend/api/papers.py`
- Modify: `backend/main.py`
- Create: `tests/backend/test_api/__init__.py`
- Create: `tests/backend/test_api/test_papers.py`

- [ ] **Step 1: Write the failing tests**

```python
import json

import pytest
from httpx import ASGITransport, AsyncClient

from backend.core.database import Database
from backend.main import create_app


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
async def client(db):
    app = create_app(db=db)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _insert_paper(db, paper_id="paper-001", title="Test Paper", score=8.5):
    await db.execute(
        "INSERT INTO papers (id, arxiv_id, title, abstract, authors, arxiv_categories, "
        "published_date, first_seen_at, updated_at) "
        "VALUES (?, ?, ?, 'Abstract text.', '[\"Author A\"]', '[\"cs.CL\"]', "
        "'2024-01-15', '2024-01-16 08:00:00', datetime('now'))",
        (paper_id, "2401.00001", title),
    )
    ar_id = await db.execute(
        "INSERT INTO analysis_runs (paper_id, factual_summary, methodology_inference, "
        "innovation_points, key_takeaways, score_total, score_breakdown, tags, "
        "evidence_level, analysis_basis, evidence_citations, confidence, status, analyzed_at) "
        "VALUES (?, '摘要', '方法', '[]', '[]', ?, '{}', '[\"nlp\"]', 'strong', "
        "'full_text', '[]', 0.8, 'succeeded', datetime('now'))",
        (paper_id, score),
    )
    await db.execute(
        "INSERT INTO paper_analysis (paper_id, active_analysis_run_id, active_analyzed_at) "
        "VALUES (?, ?, datetime('now'))",
        (paper_id, ar_id),
    )


async def test_list_papers_empty(client):
    resp = await client.get("/api/papers")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1


async def test_list_papers_with_data(client, db):
    await _insert_paper(db, "paper-001", "Paper One", 8.0)
    await _insert_paper(db, "paper-002", "Paper Two", 9.0)

    resp = await client.get("/api/papers")
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


async def test_list_papers_pagination(client, db):
    for i in range(5):
        await _insert_paper(db, f"paper-{i:03d}", f"Paper {i}", 7.0 + i)

    resp = await client.get("/api/papers?page=1&page_size=2")
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["page_size"] == 2


async def test_list_papers_filter_score_min(client, db):
    await _insert_paper(db, "paper-001", "Low Score", 5.0)
    await _insert_paper(db, "paper-002", "High Score", 9.0)

    resp = await client.get("/api/papers?score_min=8.0")
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "High Score"


async def test_get_paper_detail(client, db):
    await _insert_paper(db, "paper-001", "Detail Paper", 8.5)
    await db.execute(
        "INSERT INTO paper_sources (paper_id, source_name, source_url, collected_at) "
        "VALUES ('paper-001', 'huggingface', 'https://hf.co/papers/2401.00001', datetime('now'))"
    )

    resp = await client.get("/api/papers/paper-001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Detail Paper"
    assert data["analysis"]["score_total"] == 8.5
    assert len(data["sources"]) == 1


async def test_get_paper_not_found(client):
    resp = await client.get("/api/papers/nonexistent")
    assert resp.status_code == 404


async def test_health_still_works(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
```

- [ ] **Step 2: Write deps.py**

```python
from __future__ import annotations

from backend.core.database import Database
from backend.core.stage_runner import StageRunner

_db_instance: Database | None = None
_stage_runner_instance: StageRunner | None = None


def set_db(db: Database) -> None:
    global _db_instance, _stage_runner_instance
    _db_instance = db
    _stage_runner_instance = StageRunner(db)


def get_db() -> Database:
    assert _db_instance is not None, "Database not initialized"
    return _db_instance


def get_stage_runner() -> StageRunner:
    assert _stage_runner_instance is not None, "StageRunner not initialized"
    return _stage_runner_instance
```

- [ ] **Step 3: Write papers.py**

```python
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query

from backend.api.deps import get_db

router = APIRouter(prefix="/api/papers", tags=["papers"])


@router.get("")
async def list_papers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    score_min: float | None = Query(None),
    q: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    tag: str | None = Query(None),
    sort: str = Query("updated_at_desc"),
):
    db = get_db()
    conditions = []
    params: list = []

    if score_min is not None:
        conditions.append("ar.score_total >= ?")
        params.append(score_min)
    if q:
        conditions.append("(p.title LIKE ? OR p.abstract LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    if date_from:
        conditions.append("p.first_seen_at >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("p.first_seen_at <= ?")
        params.append(date_to)
    if tag:
        conditions.append("ar.tags LIKE ?")
        params.append(f"%{tag}%")

    where = " AND ".join(conditions) if conditions else "1=1"

    sort_map = {
        "updated_at_desc": "p.updated_at DESC",
        "updated_at_asc": "p.updated_at ASC",
        "score_desc": "ar.score_total DESC",
        "score_asc": "ar.score_total ASC",
    }
    order_by = sort_map.get(sort, "p.updated_at DESC")

    count_row = await db.fetch_one(
        f"SELECT COUNT(*) as cnt FROM papers p "
        f"LEFT JOIN paper_analysis pa ON pa.paper_id = p.id "
        f"LEFT JOIN analysis_runs ar ON ar.id = pa.active_analysis_run_id "
        f"WHERE {where}",
        tuple(params),
    )
    total = count_row["cnt"] if count_row else 0

    offset = (page - 1) * page_size
    rows = await db.fetch_all(
        f"SELECT p.id, p.title, p.arxiv_id, p.published_date, p.first_seen_at, "
        f"ar.score_total, ar.tags, ar.analysis_basis, ar.evidence_level "
        f"FROM papers p "
        f"LEFT JOIN paper_analysis pa ON pa.paper_id = p.id "
        f"LEFT JOIN analysis_runs ar ON ar.id = pa.active_analysis_run_id "
        f"WHERE {where} ORDER BY {order_by} LIMIT ? OFFSET ?",
        tuple(params) + (page_size, offset),
    )

    items = []
    for r in rows:
        tags = []
        if r["tags"]:
            try:
                tags = json.loads(r["tags"])
            except (json.JSONDecodeError, TypeError):
                pass
        items.append({
            "id": r["id"],
            "title": r["title"],
            "arxiv_id": r["arxiv_id"],
            "published_date": r["published_date"],
            "first_seen_at": r["first_seen_at"],
            "score_total": r["score_total"],
            "tags": tags,
            "analysis_basis": r["analysis_basis"],
            "evidence_level": r["evidence_level"],
        })

    return {"items": items, "page": page, "page_size": page_size, "total": total}


@router.get("/{paper_id}")
async def get_paper(paper_id: str):
    db = get_db()
    paper = await db.fetch_one("SELECT * FROM papers WHERE id = ?", (paper_id,))
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    paper_dict = dict(paper)
    for field in ["authors", "arxiv_categories"]:
        if paper_dict.get(field) and isinstance(paper_dict[field], str):
            try:
                paper_dict[field] = json.loads(paper_dict[field])
            except (json.JSONDecodeError, TypeError):
                pass

    analysis = None
    pa = await db.fetch_one(
        "SELECT * FROM paper_analysis WHERE paper_id = ?", (paper_id,)
    )
    if pa:
        ar = await db.fetch_one(
            "SELECT * FROM analysis_runs WHERE id = ?", (pa["active_analysis_run_id"],)
        )
        if ar:
            ar_dict = dict(ar)
            for field in ["innovation_points", "key_takeaways", "score_breakdown",
                          "tags", "evidence_citations"]:
                if ar_dict.get(field) and isinstance(ar_dict[field], str):
                    try:
                        ar_dict[field] = json.loads(ar_dict[field])
                    except (json.JSONDecodeError, TypeError):
                        pass
            analysis = ar_dict

    sources = await db.fetch_all(
        "SELECT * FROM paper_sources WHERE paper_id = ?", (paper_id,)
    )

    return {
        **paper_dict,
        "analysis": analysis,
        "sources": [dict(s) for s in sources],
    }
```

- [ ] **Step 4: Update main.py**

```python
from __future__ import annotations

from fastapi import FastAPI

from backend.api.deps import set_db
from backend.core.database import Database


def create_app(db: Database | None = None) -> FastAPI:
    app = FastAPI(title="LLM Paper Tracker", version="0.1.0")

    if db is not None:
        set_db(db)

    from backend.api.papers import router as papers_router
    app.include_router(papers_router)

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    return app


app = create_app()
```

- [ ] **Step 5: Run tests, lint, commit**

```bash
pytest tests/backend/test_api/test_papers.py -v
ruff check backend/api/ backend/main.py tests/backend/test_api/
git commit -m "feat: papers API with list, detail, pagination, and filtering"
```

---

### Task 2: Reports API

**Files:**
- Create: `backend/api/reports.py`
- Create: `tests/backend/test_api/test_reports.py`

- [ ] **Step 1: Write the failing tests**

```python
import pytest
from httpx import ASGITransport, AsyncClient

from backend.core.database import Database
from backend.main import create_app


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
async def client(db):
    app = create_app(db=db)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _insert_report(db, week_start="2024-01-15", week_end="2024-01-21"):
    return await db.execute(
        "INSERT INTO weekly_reports (week_start, week_end, report_content, "
        "highlights, is_current, created_at) "
        "VALUES (?, ?, '# Week Report\nContent here.', '[]', 1, datetime('now'))",
        (week_start, week_end),
    )


async def test_list_reports_empty(client):
    resp = await client.get("/api/reports")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


async def test_list_reports_with_data(client, db):
    await _insert_report(db, "2024-01-15", "2024-01-21")
    await _insert_report(db, "2024-01-22", "2024-01-28")

    resp = await client.get("/api/reports")
    data = resp.json()
    assert data["total"] == 2


async def test_get_report_detail(client, db):
    report_id = await _insert_report(db)

    resp = await client.get(f"/api/reports/{report_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["week_start"] == "2024-01-15"
    assert "Content here." in data["report_content"]


async def test_get_report_not_found(client):
    resp = await client.get("/api/reports/999")
    assert resp.status_code == 404
```

- [ ] **Step 2: Write the implementation**

```python
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query

from backend.api.deps import get_db

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("")
async def list_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    db = get_db()

    count_row = await db.fetch_one("SELECT COUNT(*) as cnt FROM weekly_reports")
    total = count_row["cnt"] if count_row else 0

    offset = (page - 1) * page_size
    rows = await db.fetch_all(
        "SELECT id, week_start, week_end, cluster_run_id, is_current, created_at "
        "FROM weekly_reports ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (page_size, offset),
    )

    items = [dict(r) for r in rows]
    return {"items": items, "page": page, "page_size": page_size, "total": total}


@router.get("/{report_id}")
async def get_report(report_id: int):
    db = get_db()
    row = await db.fetch_one("SELECT * FROM weekly_reports WHERE id = ?", (report_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")

    result = dict(row)
    for field in ["analysis_run_ids_json", "highlights"]:
        if result.get(field) and isinstance(result[field], str):
            try:
                result[field] = json.loads(result[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return result
```

- [ ] **Step 3: Register router in main.py, run tests, lint, commit**

Add to `create_app()` in main.py:
```python
from backend.api.reports import router as reports_router
app.include_router(reports_router)
```

```bash
pytest tests/backend/test_api/test_reports.py -v
ruff check backend/api/ tests/backend/test_api/
git commit -m "feat: reports API with list and detail endpoints"
```

---

### Task 3: Semantic Search and Jobs API

**Files:**
- Create: `backend/api/search.py`
- Create: `backend/api/jobs.py`
- Create: `tests/backend/test_api/test_search.py`
- Create: `tests/backend/test_api/test_jobs.py`

- [ ] **Step 1: Write the failing tests for search**

```python
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.deps import set_embedding_client, set_vector_store
from backend.core.database import Database
from backend.main import create_app


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
def mock_embedding():
    client = AsyncMock()
    client.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
    return client


@pytest.fixture
def mock_vector_store():
    store = MagicMock()
    store.query = MagicMock(return_value={
        "ids": [["paper-001"]],
        "distances": [[0.15]],
    })
    return store


@pytest.fixture
async def client(db, mock_embedding, mock_vector_store):
    app = create_app(db=db)
    set_embedding_client(mock_embedding)
    set_vector_store(mock_vector_store)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_semantic_search(client, db, mock_embedding, mock_vector_store):
    await db.execute(
        "INSERT INTO papers (id, title, abstract, first_seen_at, updated_at) "
        "VALUES ('paper-001', 'RLHF Paper', 'Abstract', datetime('now'), datetime('now'))"
    )

    resp = await client.post("/api/search/semantic", json={"query": "RLHF alignment", "top_k": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) == 1
    assert data["results"][0]["paper_id"] == "paper-001"
    mock_embedding.embed.assert_called_once()
    mock_vector_store.query.assert_called_once()
```

- [ ] **Step 2: Write the failing tests for jobs**

```python
import pytest
from httpx import ASGITransport, AsyncClient

from backend.core.database import Database
from backend.core.stage_runner import StageRunner
from backend.main import create_app


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
async def client(db):
    app = create_app(db=db)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_retry_stage(client, db):
    runner = StageRunner(db)
    run_id = await runner.create("paper", "paper-001", "analyzer")
    task = await runner.claim("analyzer", "worker-1")
    await runner.fail(task["id"], "some error")

    resp = await client.post("/api/stages/retry", json={
        "stage_run_id": run_id,
        "reason": "manual_retry",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "accepted"

    row = await db.fetch_one("SELECT * FROM stage_runs WHERE id = ?", (run_id,))
    assert row["status"] == "pending"
```

- [ ] **Step 3: Write search.py**

```python
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.api.deps import get_db, get_embedding_client, get_vector_store

router = APIRouter(prefix="/api/search", tags=["search"])


class SemanticSearchRequest(BaseModel):
    query: str
    top_k: int = Field(10, ge=1, le=100)
    collection: str = "paper_embeddings_v1"


@router.post("/semantic")
async def semantic_search(req: SemanticSearchRequest):
    db = get_db()
    embedding_client = get_embedding_client()
    vector_store = get_vector_store()

    query_embedding = await embedding_client.embed([req.query])
    if not query_embedding:
        return {"results": []}

    results = vector_store.query(
        collection_name=req.collection,
        query_embeddings=query_embedding,
        n_results=req.top_k,
    )

    result_ids = results.get("ids", [[]])[0]
    distances = results.get("distances", [[]])[0]

    items = []
    for pid, dist in zip(result_ids, distances):
        paper = await db.fetch_one(
            "SELECT id, title, abstract FROM papers WHERE id = ?", (pid,)
        )
        if paper:
            items.append({
                "paper_id": paper["id"],
                "title": paper["title"],
                "abstract": paper["abstract"],
                "distance": dist,
            })

    return {"results": items}
```

- [ ] **Step 4: Write jobs.py**

```python
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.api.deps import get_stage_runner

router = APIRouter(tags=["jobs"])


class RetryRequest(BaseModel):
    stage_run_id: int
    reason: str = ""


@router.post("/api/stages/retry")
async def retry_stage(req: RetryRequest):
    stage_runner = get_stage_runner()
    try:
        await stage_runner.retry(req.stage_run_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "status": "accepted",
        "stage_run_id": req.stage_run_id,
        "accepted_at": datetime.utcnow().isoformat(),
    }
```

- [ ] **Step 5: Update deps.py for embedding/vector store**

Add to `deps.py`:
```python
_embedding_client = None
_vector_store = None

def set_embedding_client(client) -> None:
    global _embedding_client
    _embedding_client = client

def get_embedding_client():
    assert _embedding_client is not None, "EmbeddingClient not initialized"
    return _embedding_client

def set_vector_store(store) -> None:
    global _vector_store
    _vector_store = store

def get_vector_store():
    assert _vector_store is not None, "VectorStore not initialized"
    return _vector_store
```

- [ ] **Step 6: Register routers in main.py, run tests, lint, commit**

```python
from backend.api.search import router as search_router
from backend.api.jobs import router as jobs_router
app.include_router(search_router)
app.include_router(jobs_router)
```

```bash
pytest tests/backend/test_api/ -v
ruff check backend/api/ backend/main.py tests/backend/test_api/
git commit -m "feat: semantic search and job retry API endpoints"
```

---

### Task 4: Full Test Suite Verification

- [ ] **Step 1: Run all tests**

Run: `pytest tests/ -v`
Expected: All pass (~155 total)

- [ ] **Step 2: Run linter**

Run: `ruff check .`
Expected: All checks passed
