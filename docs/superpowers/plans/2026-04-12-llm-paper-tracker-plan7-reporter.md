# Reporter (Plan 7) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Reporter module that performs HDBSCAN clustering on paper embeddings, generates LLM-powered Chinese weekly trend reports, stores them in `weekly_reports`, and creates sync stage_runs for Obsidian publishing.

**Architecture:** `ClusterService` reads embeddings from VectorStore, runs HDBSCAN, writes `cluster_runs`, `cluster_entities`, `cluster_versions`, and `paper_cluster_assignments`. `ReportGenerator` builds a weekly report prompt from cluster + paper data and calls LLM. `ReporterService` orchestrates: collect papers in window → cluster → generate report → store → create sync task. Weekly summary Markdown generation reuses the template from the design spec.

**Tech Stack:** hdbscan, numpy, existing LLMClient, VectorStore, Database, StageRunner from Plan 1.

---

## File Structure

| File | Responsibility |
|------|---------------|
| `backend/reporter/__init__.py` | Package init |
| `backend/reporter/cluster.py` | `ClusterService` — HDBSCAN clustering, write cluster_runs/entities/versions/assignments |
| `backend/reporter/report_prompt.py` | `build_weekly_report_prompt()` — assemble LLM prompt for weekly report |
| `backend/reporter/report_generator.py` | `generate_weekly_markdown()` — render weekly report Markdown (Chinese) |
| `backend/reporter/service.py` | `ReporterService` — orchestrate weekly report pipeline |
| `tests/backend/test_reporter/__init__.py` | Test package init |
| `tests/backend/test_reporter/test_cluster.py` | Tests for ClusterService |
| `tests/backend/test_reporter/test_report_prompt.py` | Tests for report prompt assembly |
| `tests/backend/test_reporter/test_report_generator.py` | Tests for weekly Markdown generation |
| `tests/backend/test_reporter/test_service.py` | Tests for ReporterService |

---

### Task 1: ClusterService

**Files:**
- Create: `backend/reporter/__init__.py`
- Create: `backend/reporter/cluster.py`
- Create: `tests/backend/test_reporter/__init__.py`
- Create: `tests/backend/test_reporter/test_cluster.py`

- [ ] **Step 1: Write the failing tests**

```python
import numpy as np
import pytest

from backend.core.database import Database
from backend.reporter.cluster import ClusterService


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.initialize()
    yield database
    await database.close()


def _make_embeddings(n: int, dim: int = 8, n_clusters: int = 2) -> tuple[list[str], list[list[float]]]:
    """Generate embeddings that form distinct clusters."""
    rng = np.random.RandomState(42)
    ids = [f"paper-{i:03d}" for i in range(n)]
    embeddings = []
    for i in range(n):
        cluster_id = i % n_clusters
        center = np.zeros(dim)
        center[cluster_id] = 5.0
        vec = center + rng.randn(dim) * 0.3
        embeddings.append(vec.tolist())
    return ids, embeddings


async def test_run_cluster_creates_cluster_run(db):
    svc = ClusterService(db)
    ids, embeddings = _make_embeddings(20, dim=8, n_clusters=2)

    result = await svc.run(
        paper_ids=ids,
        embeddings=embeddings,
        embedding_version_id=1,
        run_type="stable",
        window_start="2024-01-08",
        window_end="2024-01-14",
    )

    assert result["cluster_run_id"] is not None
    row = await db.fetch_one("SELECT * FROM cluster_runs WHERE id = ?", (result["cluster_run_id"],))
    assert row is not None
    assert row["run_type"] == "stable"
    assert row["paper_count"] == 20
    assert row["algorithm_name"] == "hdbscan"


async def test_run_cluster_creates_assignments(db):
    svc = ClusterService(db)
    ids, embeddings = _make_embeddings(20, dim=8, n_clusters=2)

    result = await svc.run(
        paper_ids=ids,
        embeddings=embeddings,
        embedding_version_id=1,
        run_type="stable",
    )

    assignments = await db.fetch_all(
        "SELECT * FROM paper_cluster_assignments WHERE cluster_run_id = ?",
        (result["cluster_run_id"],),
    )
    assert len(assignments) > 0
    assert all(a["assignment_type"] == "stable" for a in assignments)


async def test_run_cluster_creates_entities(db):
    svc = ClusterService(db)
    ids, embeddings = _make_embeddings(20, dim=8, n_clusters=2)

    result = await svc.run(
        paper_ids=ids,
        embeddings=embeddings,
        embedding_version_id=1,
        run_type="stable",
    )

    assert result["n_clusters"] >= 1
    entities = await db.fetch_all("SELECT * FROM cluster_entities")
    assert len(entities) >= 1


async def test_run_cluster_with_few_papers(db):
    svc = ClusterService(db)
    ids = ["paper-001", "paper-002"]
    embeddings = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]

    result = await svc.run(
        paper_ids=ids,
        embeddings=embeddings,
        embedding_version_id=1,
        run_type="provisional",
    )

    assert result["cluster_run_id"] is not None
    assert result["n_clusters"] >= 0


async def test_run_cluster_empty_input(db):
    svc = ClusterService(db)

    result = await svc.run(
        paper_ids=[],
        embeddings=[],
        embedding_version_id=1,
        run_type="provisional",
    )

    assert result["cluster_run_id"] is not None
    assert result["n_clusters"] == 0
```

- [ ] **Step 2: Write the implementation**

```python
from __future__ import annotations

import json
import logging
import uuid

import numpy as np

from backend.core.database import Database

logger = logging.getLogger(__name__)


class ClusterService:
    def __init__(self, db: Database, min_cluster_size: int = 3, min_samples: int = 2):
        self._db = db
        self._min_cluster_size = min_cluster_size
        self._min_samples = min_samples

    async def run(
        self,
        paper_ids: list[str],
        embeddings: list[list[float]],
        embedding_version_id: int,
        run_type: str = "stable",
        window_start: str | None = None,
        window_end: str | None = None,
    ) -> dict:
        cluster_run_id = await self._db.execute(
            "INSERT INTO cluster_runs (run_type, embedding_version_id, window_start, "
            "window_end, paper_count, algorithm_name, algorithm_version, "
            "cluster_params_json, is_stable, created_at) "
            "VALUES (?, ?, ?, ?, ?, 'hdbscan', '0.8', ?, ?, datetime('now'))",
            (
                run_type,
                embedding_version_id,
                window_start,
                window_end,
                len(paper_ids),
                json.dumps({
                    "min_cluster_size": self._min_cluster_size,
                    "min_samples": self._min_samples,
                }),
                run_type == "stable",
            ),
        )

        if not paper_ids or not embeddings:
            return {"cluster_run_id": cluster_run_id, "n_clusters": 0, "labels": []}

        X = np.array(embeddings)
        labels = self._cluster(X)

        unique_labels = set(labels)
        unique_labels.discard(-1)  # noise label

        entity_map: dict[int, str] = {}
        for label in sorted(unique_labels):
            entity_id = str(uuid.uuid4())
            entity_map[label] = entity_id

            await self._db.execute(
                "INSERT INTO cluster_entities (id, first_seen_run_id, current_name, "
                "status, updated_at) VALUES (?, ?, ?, 'active', datetime('now'))",
                (entity_id, cluster_run_id, f"cluster-{label}"),
            )

            version_id = await self._db.execute(
                "INSERT INTO cluster_versions (cluster_entity_id, cluster_run_id, "
                "name, change_type, created_at) "
                "VALUES (?, ?, ?, 'created', datetime('now'))",
                (entity_id, cluster_run_id, f"cluster-{label}"),
            )

        for i, (paper_id, label) in enumerate(zip(paper_ids, labels)):
            if label == -1:
                continue
            entity_id = entity_map[label]
            version_row = await self._db.fetch_one(
                "SELECT id FROM cluster_versions WHERE cluster_entity_id = ? "
                "AND cluster_run_id = ?",
                (entity_id, cluster_run_id),
            )
            if version_row:
                await self._db.execute(
                    "INSERT INTO paper_cluster_assignments (paper_id, cluster_run_id, "
                    "cluster_version_id, assignment_type, similarity_score, assigned_at) "
                    "VALUES (?, ?, ?, ?, ?, datetime('now'))",
                    (paper_id, cluster_run_id, version_row["id"], run_type, None),
                )

        return {
            "cluster_run_id": cluster_run_id,
            "n_clusters": len(unique_labels),
            "labels": labels.tolist() if isinstance(labels, np.ndarray) else labels,
        }

    def _cluster(self, X: np.ndarray) -> np.ndarray:
        if len(X) < self._min_cluster_size:
            return np.full(len(X), -1, dtype=int)

        import hdbscan

        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=self._min_cluster_size,
            min_samples=self._min_samples,
        )
        labels = clusterer.fit_predict(X)
        return labels
```

- [ ] **Step 3: Run tests, lint, commit**

```bash
pytest tests/backend/test_reporter/test_cluster.py -v
ruff check backend/reporter/ tests/backend/test_reporter/
git commit -m "feat: HDBSCAN clustering service for paper embeddings"
```

---

### Task 2: Weekly Report Prompt

**Files:**
- Create: `backend/reporter/report_prompt.py`
- Create: `tests/backend/test_reporter/test_report_prompt.py`

- [ ] **Step 1: Write the failing tests**

```python
from backend.reporter.report_prompt import build_weekly_report_prompt


def test_prompt_has_system_and_user_messages():
    cluster_summaries = [
        {
            "cluster_name": "cluster-0",
            "paper_count": 5,
            "top_papers": [
                {"title": "Paper A", "score": 9.0, "summary": "Summary A"},
                {"title": "Paper B", "score": 8.5, "summary": "Summary B"},
            ],
            "common_tags": ["rlhf", "alignment"],
        },
    ]
    messages = build_weekly_report_prompt(
        week_str="2024-W03",
        date_range="2024-01-15 ~ 2024-01-21",
        total_papers=20,
        total_analyzed=18,
        cluster_summaries=cluster_summaries,
    )

    assert len(messages) >= 2
    assert messages[0]["role"] == "system"
    assert messages[-1]["role"] == "user"


def test_prompt_includes_cluster_data():
    cluster_summaries = [
        {
            "cluster_name": "RLHF研究",
            "paper_count": 8,
            "top_papers": [
                {"title": "RLHF论文", "score": 9.2, "summary": "关于RLHF"},
            ],
            "common_tags": ["rlhf"],
        },
    ]
    messages = build_weekly_report_prompt(
        week_str="2024-W03",
        date_range="2024-01-15 ~ 2024-01-21",
        total_papers=10,
        total_analyzed=8,
        cluster_summaries=cluster_summaries,
    )
    user_msg = messages[-1]["content"]
    assert "RLHF研究" in user_msg
    assert "RLHF论文" in user_msg


def test_prompt_requests_chinese_output():
    messages = build_weekly_report_prompt(
        week_str="2024-W03",
        date_range="2024-01-15 ~ 2024-01-21",
        total_papers=0,
        total_analyzed=0,
        cluster_summaries=[],
    )
    system_msg = messages[0]["content"]
    assert "中文" in system_msg


def test_prompt_includes_week_metadata():
    messages = build_weekly_report_prompt(
        week_str="2024-W03",
        date_range="2024-01-15 ~ 2024-01-21",
        total_papers=25,
        total_analyzed=20,
        cluster_summaries=[],
    )
    user_msg = messages[-1]["content"]
    assert "2024-W03" in user_msg
    assert "25" in user_msg
```

- [ ] **Step 2: Write the implementation**

```python
from __future__ import annotations

WEEKLY_REPORT_SYSTEM_PROMPT = """你是一位 AI 研究趋势分析专家。基于本周收集和分析的论文数据，生成一份中文周报。

周报需要包含：
1. 本周趋势概述（整体方向和热点）
2. 推荐精读的论文（附推荐理由）
3. 各领域动态（按聚类分组，描述活跃度和变化）
4. 新兴信号（新出现的研究方向或跨领域关联）

输出格式为 Markdown，使用中文撰写。不要输出 JSON，直接输出 Markdown 正文。"""


def build_weekly_report_prompt(
    week_str: str,
    date_range: str,
    total_papers: int,
    total_analyzed: int,
    cluster_summaries: list[dict],
    prev_week_clusters: list[dict] | None = None,
) -> list[dict]:
    user_parts = [
        f"# {week_str} 周报数据 ({date_range})",
        "",
        f"本周采集论文 {total_papers} 篇，完成分析 {total_analyzed} 篇。",
        "",
    ]

    if cluster_summaries:
        user_parts.append("## 聚类分组")
        for i, cs in enumerate(cluster_summaries):
            name = cs.get("cluster_name", f"cluster-{i}")
            count = cs.get("paper_count", 0)
            tags = ", ".join(cs.get("common_tags", []))
            user_parts.append(f"\n### {name} ({count} 篇)")
            if tags:
                user_parts.append(f"常见标签: {tags}")
            top_papers = cs.get("top_papers", [])
            if top_papers:
                user_parts.append("代表性论文:")
                for p in top_papers:
                    title = p.get("title", "")
                    score = p.get("score", 0)
                    summary = p.get("summary", "")
                    user_parts.append(f"- {title} (评分 {score}): {summary}")
    else:
        user_parts.append("本周无聚类数据。")

    if prev_week_clusters:
        user_parts.append("\n## 上周聚类（对比参考）")
        for cs in prev_week_clusters:
            name = cs.get("cluster_name", "unknown")
            count = cs.get("paper_count", 0)
            user_parts.append(f"- {name}: {count} 篇")

    user_parts.append("\n请根据以上数据生成本周周报。")

    return [
        {"role": "system", "content": WEEKLY_REPORT_SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(user_parts)},
    ]
```

- [ ] **Step 3: Run tests, lint, commit**

```bash
pytest tests/backend/test_reporter/test_report_prompt.py -v
ruff check backend/reporter/ tests/backend/test_reporter/
git commit -m "feat: weekly report prompt templates for LLM trend analysis"
```

---

### Task 3: Weekly Report Markdown Generator

**Files:**
- Create: `backend/reporter/report_generator.py`
- Create: `tests/backend/test_reporter/test_report_generator.py`

- [ ] **Step 1: Write the failing tests**

```python
from backend.reporter.report_generator import generate_weekly_markdown


def test_weekly_markdown_basic():
    md = generate_weekly_markdown(
        week_str="2024-W03",
        date_range="01.15 - 01.21",
        cluster_run_id=42,
        llm_report_body="## 本周趋势\n这是趋势内容。",
        highlights=[
            {"title": "Top Paper", "reason": "突破性研究"},
        ],
    )

    assert "# 2024-W03 周报 (01.15 - 01.21)" in md
    assert "cluster_run_id: 42" in md
    assert "## 本周趋势" in md
    assert "这是趋势内容。" in md


def test_weekly_markdown_has_highlights():
    md = generate_weekly_markdown(
        week_str="2024-W03",
        date_range="01.15 - 01.21",
        cluster_run_id=1,
        llm_report_body="报告内容",
        highlights=[
            {"title": "Paper A", "reason": "重要发现"},
            {"title": "Paper B", "reason": "新方法"},
        ],
    )

    assert "## 推荐精读" in md
    assert "[[Paper A]]" in md
    assert "重要发现" in md
    assert "[[Paper B]]" in md


def test_weekly_markdown_no_highlights():
    md = generate_weekly_markdown(
        week_str="2024-W03",
        date_range="01.15 - 01.21",
        cluster_run_id=1,
        llm_report_body="报告内容",
        highlights=[],
    )

    assert "# 2024-W03 周报" in md
    assert "报告内容" in md
```

- [ ] **Step 2: Write the implementation**

```python
from __future__ import annotations


def generate_weekly_markdown(
    week_str: str,
    date_range: str,
    cluster_run_id: int | None,
    llm_report_body: str,
    highlights: list[dict] | None = None,
) -> str:
    lines = [
        f"# {week_str} 周报 ({date_range})",
        "",
    ]

    if cluster_run_id is not None:
        lines.append(f"> cluster_run_id: {cluster_run_id}")
        lines.append("")

    if highlights:
        lines.append("## 推荐精读")
        for h in highlights:
            title = h.get("title", "")
            reason = h.get("reason", "")
            lines.append(f"- [[{title}]] — {reason}")
        lines.append("")

    lines.append(llm_report_body)
    lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 3: Run tests, lint, commit**

```bash
pytest tests/backend/test_reporter/test_report_generator.py -v
ruff check backend/reporter/ tests/backend/test_reporter/
git commit -m "feat: weekly report Markdown generator for Obsidian"
```

---

### Task 4: ReporterService

**Files:**
- Create: `backend/reporter/service.py`
- Create: `tests/backend/test_reporter/test_service.py`

- [ ] **Step 1: Write the failing tests**

```python
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

    cluster_run = await db.fetch_one("SELECT * FROM cluster_runs WHERE id = ?", (row["cluster_run_id"],))
    assert cluster_run is not None
    assert cluster_run["run_type"] == "stable"


async def test_generate_report_with_no_papers(service, db, mock_vector_store):
    mock_vector_store.get = MagicMock(return_value={"ids": [[]], "embeddings": [[]]})

    report_id = await service.generate_report(week_start="2024-01-15", week_end="2024-01-21")

    assert report_id is not None
    row = await db.fetch_one("SELECT * FROM weekly_reports WHERE id = ?", (report_id,))
    assert row is not None
```

- [ ] **Step 2: Write the implementation**

```python
from __future__ import annotations

import json
import logging
from datetime import date, timedelta

from backend.core.database import Database
from backend.core.stage_runner import StageRunner
from backend.reporter.cluster import ClusterService
from backend.reporter.report_prompt import build_weekly_report_prompt
from backend.reporter.report_generator import generate_weekly_markdown

logger = logging.getLogger(__name__)


class ReporterService:
    def __init__(
        self,
        db: Database,
        stage_runner: StageRunner,
        llm_client,
        vector_store,
        embedding_collection: str = "paper_embeddings_v1",
        embedding_version_id: int = 1,
    ):
        self._db = db
        self._stage_runner = stage_runner
        self._llm = llm_client
        self._vector_store = vector_store
        self._embedding_collection = embedding_collection
        self._embedding_version_id = embedding_version_id
        self._cluster_service = ClusterService(db)

    async def generate_report(
        self,
        week_start: str,
        week_end: str,
    ) -> int:
        # 1. Get papers analyzed in this window
        papers = await self._db.fetch_all(
            "SELECT p.id, p.title, ar.factual_summary, ar.score_total, ar.tags "
            "FROM paper_analysis pa "
            "JOIN papers p ON pa.paper_id = p.id "
            "JOIN analysis_runs ar ON pa.active_analysis_run_id = ar.id "
            "WHERE pa.active_analyzed_at >= ? AND pa.active_analyzed_at < date(?, '+1 day')",
            (week_start, week_end),
        )
        paper_ids = [p["id"] for p in papers]

        # 2. Get embeddings from vector store
        embeddings_data = self._vector_store.get(
            collection_name=self._embedding_collection,
            ids=paper_ids if paper_ids else ["__nonexistent__"],
            include=["embeddings"],
        )

        valid_ids = embeddings_data.get("ids", [[]])[0]
        valid_embeddings = embeddings_data.get("embeddings", [[]])[0]

        # 3. Run clustering
        cluster_result = await self._cluster_service.run(
            paper_ids=valid_ids,
            embeddings=valid_embeddings,
            embedding_version_id=self._embedding_version_id,
            run_type="stable",
            window_start=week_start,
            window_end=week_end,
        )

        # 4. Build cluster summaries
        cluster_summaries = await self._build_cluster_summaries(
            cluster_result, papers, valid_ids,
        )

        # 5. Compute week string
        ws = date.fromisoformat(week_start)
        we = date.fromisoformat(week_end)
        iso_week = ws.isocalendar()
        week_str = f"{iso_week[0]}-W{iso_week[1]:02d}"
        date_range = f"{ws.strftime('%m.%d')} - {we.strftime('%m.%d')}"

        # 6. Call LLM
        messages = build_weekly_report_prompt(
            week_str=week_str,
            date_range=date_range,
            total_papers=len(papers),
            total_analyzed=len(papers),
            cluster_summaries=cluster_summaries,
        )
        llm_report = await self._llm.chat(messages)

        # 7. Build highlights from top-scoring papers
        sorted_papers = sorted(papers, key=lambda p: p["score_total"] or 0, reverse=True)
        highlights = []
        for p in sorted_papers[:5]:
            if (p["score_total"] or 0) >= 8.0:
                highlights.append({
                    "title": p["title"],
                    "reason": (p["factual_summary"] or "")[:60],
                })

        # 8. Generate full markdown
        full_report = generate_weekly_markdown(
            week_str=week_str,
            date_range=date_range,
            cluster_run_id=cluster_result["cluster_run_id"],
            llm_report_body=llm_report,
            highlights=highlights,
        )

        # 9. Store weekly report
        analysis_run_ids = [p["id"] for p in papers]
        report_id = await self._db.execute(
            "INSERT INTO weekly_reports (week_start, week_end, cluster_run_id, "
            "analysis_run_ids_json, report_content, highlights, is_current, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 1, datetime('now'))",
            (
                week_start,
                week_end,
                cluster_result["cluster_run_id"],
                json.dumps(analysis_run_ids),
                full_report,
                json.dumps(highlights),
            ),
        )

        # 10. Create sync stage_run
        await self._stage_runner.create(
            target_type="report",
            target_id=str(report_id),
            stage="sync",
        )

        return report_id

    async def _build_cluster_summaries(
        self, cluster_result: dict, papers: list, valid_ids: list[str]
    ) -> list[dict]:
        if not cluster_result.get("labels"):
            return []

        labels = cluster_result["labels"]
        id_to_label = {}
        for pid, label in zip(valid_ids, labels):
            if label >= 0:
                id_to_label[pid] = label

        paper_map = {p["id"]: p for p in papers}
        clusters: dict[int, list[dict]] = {}
        for pid, label in id_to_label.items():
            if pid in paper_map:
                clusters.setdefault(label, []).append(paper_map[pid])

        summaries = []
        for label, cluster_papers in sorted(clusters.items()):
            sorted_cp = sorted(cluster_papers, key=lambda p: p["score_total"] or 0, reverse=True)
            all_tags = []
            for p in cluster_papers:
                tags_raw = p.get("tags", "[]")
                if isinstance(tags_raw, str):
                    try:
                        all_tags.extend(json.loads(tags_raw))
                    except (json.JSONDecodeError, TypeError):
                        pass
                elif isinstance(tags_raw, list):
                    all_tags.extend(tags_raw)

            top_papers = [
                {
                    "title": p["title"],
                    "score": p["score_total"],
                    "summary": (p["factual_summary"] or "")[:80],
                }
                for p in sorted_cp[:3]
            ]

            common_tags = list(dict.fromkeys(all_tags))[:5]

            summaries.append({
                "cluster_name": f"cluster-{label}",
                "paper_count": len(cluster_papers),
                "top_papers": top_papers,
                "common_tags": common_tags,
            })

        return summaries
```

- [ ] **Step 3: Run tests, lint, commit**

```bash
pytest tests/backend/test_reporter/test_service.py -v
ruff check backend/reporter/ tests/backend/test_reporter/
git commit -m "feat: reporter service with clustering and LLM weekly report generation"
```

---

### Task 5: Full Test Suite Verification

- [ ] **Step 1: Run all tests**

Run: `pytest tests/ -v`
Expected: All pass (~140 total)

- [ ] **Step 2: Run linter**

Run: `ruff check .`
Expected: All checks passed
