# Obsidian Sync (Plan 6) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Obsidian Sync service that claims `sync` stage_runs, generates Chinese-language Markdown notes for individual papers and daily summaries, writes them to the Obsidian vault directory, and records each sync in `sync_log` with checksum-based idempotency.

**Architecture:** `ObsidianSyncService` claims sync tasks via StageRunner, loads the paper + analysis data from the DB, calls `NoteGenerator` to produce a single-paper Markdown note (Chinese), calls `DailySummaryGenerator` to produce/update the daily digest, writes files to the vault under `LLM-Research/{YYYY-Www}/{YYYY-MM-DD}/`, and records entries in `sync_log`. Repeated syncs with the same checksum are idempotent (skip write). Weekly summary generation is deferred to Plan 7 (Reporter).

**Tech Stack:** existing Database, StageRunner from Plan 1. hashlib for checksums, pathlib for file I/O, json for parsing stored JSON columns.

---

## File Structure

| File | Responsibility |
|------|---------------|
| `backend/sync/__init__.py` | Package init |
| `backend/sync/note_generator.py` | `generate_paper_note()` — render single-paper Markdown (Chinese) with frontmatter |
| `backend/sync/daily_summary.py` | `generate_daily_summary()` — render daily digest Markdown (Chinese) |
| `backend/sync/service.py` | `ObsidianSyncService` — claim sync tasks, generate notes, write to vault, record sync_log |
| `tests/backend/test_sync/__init__.py` | Test package init |
| `tests/backend/test_sync/test_note_generator.py` | Tests for single-paper note generation |
| `tests/backend/test_sync/test_daily_summary.py` | Tests for daily summary generation |
| `tests/backend/test_sync/test_service.py` | Tests for ObsidianSyncService |

---

### Task 1: Note Generator

**Files:**
- Create: `backend/sync/__init__.py`
- Create: `backend/sync/note_generator.py`
- Create: `tests/backend/test_sync/__init__.py`
- Create: `tests/backend/test_sync/test_note_generator.py`

- [ ] **Step 1: Write the failing tests**

```python
from backend.sync.note_generator import generate_paper_note


def test_basic_note_has_frontmatter():
    paper = {
        "id": "2401.00001",
        "title": "Scaling Laws for Neural Language Models",
        "abstract": "We study empirical scaling laws.",
        "arxiv_id": "2401.00001",
        "published_date": "2024-01-15",
        "first_seen_at": "2024-01-16 08:00:00",
    }
    analysis = {
        "factual_summary": "本文研究了神经语言模型的缩放定律。",
        "methodology_inference": "通过不同模型规模的实证评估。",
        "innovation_points": '["提出新的缩放预测方法"]',
        "key_takeaways": '["更大的模型更高效"]',
        "score_total": 8.5,
        "tags": '["scaling-laws", "language-models"]',
        "evidence_level": "strong",
        "confidence": 0.85,
        "evidence_citations": '[{"claim": "缩放遵循幂律", "source": "full_text", "page": 3}]',
        "analysis_basis": "full_text",
    }
    source = {
        "source_url": "https://huggingface.co/papers/2401.00001",
    }

    note = generate_paper_note(paper, analysis, source)

    assert "---" in note
    assert "score: 8.5" in note
    assert 'arxiv: "2401.00001"' in note
    assert "published_date: 2024-01-15" in note
    assert "collected_date: 2024-01-16" in note
    assert "evidence_level: strong" in note
    assert "confidence: 0.85" in note


def test_note_has_chinese_sections():
    paper = {
        "id": "2401.00001",
        "title": "Test Paper",
        "abstract": "Abstract text.",
        "arxiv_id": "2401.00001",
        "published_date": "2024-01-15",
        "first_seen_at": "2024-01-16 08:00:00",
    }
    analysis = {
        "factual_summary": "这是事实摘要。",
        "methodology_inference": "这是方法推断。",
        "innovation_points": '["创新点一", "创新点二"]',
        "key_takeaways": '["结论一"]',
        "score_total": 7.0,
        "tags": '["nlp"]',
        "evidence_level": "moderate",
        "confidence": 0.7,
        "evidence_citations": '[]',
        "analysis_basis": "abstract_only",
    }

    note = generate_paper_note(paper, analysis)

    assert "# Test Paper" in note
    assert "## 事实摘要" in note
    assert "这是事实摘要。" in note
    assert "## 推断性方法总结" in note
    assert "这是方法推断。" in note
    assert "## 创新点" in note
    assert "- 创新点一" in note
    assert "- 创新点二" in note
    assert "## 关键结论" in note
    assert "- 结论一" in note
    assert "## 链接" in note


def test_note_with_evidence_citations():
    paper = {
        "id": "2401.00001",
        "title": "Test",
        "abstract": "A",
        "arxiv_id": "2401.00001",
        "published_date": None,
        "first_seen_at": "2024-01-16 08:00:00",
    }
    analysis = {
        "factual_summary": "摘要",
        "methodology_inference": "方法",
        "innovation_points": '[]',
        "key_takeaways": '[]',
        "score_total": 5.0,
        "tags": '[]',
        "evidence_level": "limited",
        "confidence": 0.5,
        "evidence_citations": '[{"claim": "主要发现", "source": "full_text", "page": 3}]',
        "analysis_basis": "full_text",
    }

    note = generate_paper_note(paper, analysis)

    assert "## 证据引用" in note
    assert "主要发现" in note
    assert "p.3" in note


def test_note_without_source():
    paper = {
        "id": "2401.00001",
        "title": "Test",
        "abstract": "A",
        "arxiv_id": "2401.00001",
        "published_date": None,
        "first_seen_at": "2024-01-16 08:00:00",
    }
    analysis = {
        "factual_summary": "摘要",
        "methodology_inference": "方法",
        "innovation_points": '[]',
        "key_takeaways": '[]',
        "score_total": 5.0,
        "tags": '[]',
        "evidence_level": "limited",
        "confidence": 0.5,
        "evidence_citations": '[]',
        "analysis_basis": "abstract_only",
    }

    note = generate_paper_note(paper, analysis, source=None)

    assert "arXiv: https://arxiv.org/abs/2401.00001" in note
    assert "## 链接" in note
```

- [ ] **Step 2: Write the implementation**

```python
from __future__ import annotations

import json


def _parse_json_field(value: str | list) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def generate_paper_note(
    paper: dict,
    analysis: dict,
    source: dict | None = None,
) -> str:
    arxiv_id = paper.get("arxiv_id", "")
    title = paper.get("title", "Untitled")
    published_date = paper.get("published_date") or ""
    first_seen = paper.get("first_seen_at", "")
    collected_date = first_seen[:10] if first_seen else ""

    tags = _parse_json_field(analysis.get("tags", "[]"))
    score = analysis.get("score_total", 0)
    evidence_level = analysis.get("evidence_level", "limited")
    confidence = analysis.get("confidence", 0)

    # Frontmatter
    tags_str = ", ".join(tags) if tags else ""
    lines = [
        "---",
        f"tags: [{tags_str}]",
        f"score: {score}",
        f'arxiv: "{arxiv_id}"',
        f"published_date: {published_date}" if published_date else "published_date:",
        f"collected_date: {collected_date}" if collected_date else "collected_date:",
        f"evidence_level: {evidence_level}",
        f"confidence: {confidence}",
        "---",
        "",
        f"# {title}",
        "",
    ]

    # 事实摘要
    lines.append("## 事实摘要")
    lines.append(analysis.get("factual_summary", ""))
    lines.append("")

    # 推断性方法总结
    lines.append("## 推断性方法总结")
    lines.append(analysis.get("methodology_inference", ""))
    lines.append("")

    # 创新点
    innovation_points = _parse_json_field(analysis.get("innovation_points", "[]"))
    lines.append("## 创新点")
    if innovation_points:
        for point in innovation_points:
            lines.append(f"- {point}")
    else:
        lines.append("- （无）")
    lines.append("")

    # 关键结论
    key_takeaways = _parse_json_field(analysis.get("key_takeaways", "[]"))
    lines.append("## 关键结论")
    if key_takeaways:
        for takeaway in key_takeaways:
            lines.append(f"- {takeaway}")
    else:
        lines.append("- （无）")
    lines.append("")

    # 证据引用
    evidence_citations = _parse_json_field(analysis.get("evidence_citations", "[]"))
    if evidence_citations:
        lines.append("## 证据引用")
        for cite in evidence_citations:
            claim = cite.get("claim", "")
            page = cite.get("page")
            source_type = cite.get("source", "")
            if page:
                lines.append(f"- p.{page}: {claim}")
            else:
                lines.append(f"- [{source_type}] {claim}")
        lines.append("")

    # 链接
    lines.append("## 链接")
    if arxiv_id:
        lines.append(f"- arXiv: https://arxiv.org/abs/{arxiv_id}")
    if source and source.get("source_url"):
        lines.append(f"- HuggingFace: {source['source_url']}")
    lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 3: Run tests, lint, commit**

```bash
pytest tests/backend/test_sync/test_note_generator.py -v
ruff check backend/sync/ tests/backend/test_sync/
git commit -m "feat: Chinese markdown note generator for Obsidian paper notes"
```

---

### Task 2: Daily Summary Generator

**Files:**
- Create: `backend/sync/daily_summary.py`
- Create: `tests/backend/test_sync/test_daily_summary.py`

- [ ] **Step 1: Write the failing tests**

```python
from backend.sync.daily_summary import generate_daily_summary


def test_daily_summary_basic():
    papers = [
        {
            "title": "High Score Paper",
            "score_total": 9.2,
            "tags": '["training/rlhf"]',
            "factual_summary": "一句话概要高分",
            "analysis_basis": "full_text",
            "evidence_level": "strong",
        },
        {
            "title": "Medium Score Paper",
            "score_total": 6.5,
            "tags": '["inference"]',
            "factual_summary": "一句话概要中分",
            "analysis_basis": "abstract_only",
            "evidence_level": "moderate",
        },
    ]

    md = generate_daily_summary("2024-01-15", papers, total_collected=5, total_analyzed=2)

    assert "# 2024-01-15 论文日报" in md
    assert "**5**" in md
    assert "**2**" in md
    assert "**1**" in md  # 1 high-score paper (>=8.0)


def test_daily_summary_high_score_section():
    papers = [
        {
            "title": "Top Paper",
            "score_total": 9.0,
            "tags": '["nlp"]',
            "factual_summary": "非常重要的发现",
            "analysis_basis": "full_text",
            "evidence_level": "strong",
        },
    ]

    md = generate_daily_summary("2024-01-15", papers, total_collected=1, total_analyzed=1)

    assert "## 高分文章" in md
    assert "[[Top Paper]]" in md
    assert "(9.0)" in md


def test_daily_summary_table():
    papers = [
        {
            "title": "Paper A",
            "score_total": 7.5,
            "tags": '["tag1"]',
            "factual_summary": "摘要A",
            "analysis_basis": "full_text",
            "evidence_level": "strong",
        },
    ]

    md = generate_daily_summary("2024-01-15", papers, total_collected=1, total_analyzed=1)

    assert "## 全部文章" in md
    assert "| 论文 | 评分 | 暂定领域 | 阅读基础 | 证据级别 |" in md
    assert "[[Paper A]]" in md
    assert "7.5" in md


def test_daily_summary_empty():
    md = generate_daily_summary("2024-01-15", [], total_collected=0, total_analyzed=0)
    assert "# 2024-01-15 论文日报" in md
    assert "**0**" in md


def test_daily_summary_sorts_by_score():
    papers = [
        {
            "title": "Low",
            "score_total": 5.0,
            "tags": '["a"]',
            "factual_summary": "低分",
            "analysis_basis": "abstract_only",
            "evidence_level": "limited",
        },
        {
            "title": "High",
            "score_total": 9.5,
            "tags": '["b"]',
            "factual_summary": "高分",
            "analysis_basis": "full_text",
            "evidence_level": "strong",
        },
    ]

    md = generate_daily_summary("2024-01-15", papers, total_collected=2, total_analyzed=2)

    high_pos = md.index("[[High]]")
    low_pos = md.index("[[Low]]")
    assert high_pos < low_pos
```

- [ ] **Step 2: Write the implementation**

```python
from __future__ import annotations

import json

HIGH_SCORE_THRESHOLD = 8.0


def _parse_json_field(value: str | list) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def _first_tag(tags_raw) -> str:
    tags = _parse_json_field(tags_raw)
    return f"#{tags[0]}" if tags else ""


def _summary_oneliner(summary: str, max_len: int = 40) -> str:
    line = summary.replace("\n", " ").strip()
    if len(line) > max_len:
        return line[:max_len] + "…"
    return line


def generate_daily_summary(
    date_str: str,
    papers: list[dict],
    total_collected: int = 0,
    total_analyzed: int = 0,
) -> str:
    sorted_papers = sorted(papers, key=lambda p: p.get("score_total", 0), reverse=True)
    high_score_papers = [p for p in sorted_papers if p.get("score_total", 0) >= HIGH_SCORE_THRESHOLD]

    lines = [
        f"# {date_str} 论文日报",
        "",
        f"今日采集 **{total_collected}** 篇，完成分析 **{total_analyzed}** 篇，"
        f"高分文章 **{len(high_score_papers)}** 篇",
        "",
    ]

    if high_score_papers:
        lines.append("## 高分文章")
        for p in high_score_papers:
            title = p.get("title", "Untitled")
            score = p.get("score_total", 0)
            summary = _summary_oneliner(p.get("factual_summary", ""))
            tag = _first_tag(p.get("tags", "[]"))
            tag_suffix = f" {tag}" if tag else ""
            lines.append(f"- [[{title}]] ({score}) — {summary}{tag_suffix}")
        lines.append("")

    lines.append("## 全部文章")
    lines.append("| 论文 | 评分 | 暂定领域 | 阅读基础 | 证据级别 |")
    lines.append("|------|------|----------|----------|----------|")
    for p in sorted_papers:
        title = p.get("title", "Untitled")
        score = p.get("score_total", 0)
        tag = _first_tag(p.get("tags", "[]"))
        basis = p.get("analysis_basis", "abstract_only")
        evidence = p.get("evidence_level", "limited")
        lines.append(f"| [[{title}]] | {score} | {tag} | {basis} | {evidence} |")
    lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 3: Run tests, lint, commit**

```bash
pytest tests/backend/test_sync/test_daily_summary.py -v
ruff check backend/sync/ tests/backend/test_sync/
git commit -m "feat: daily summary generator for Obsidian daily digest"
```

---

### Task 3: ObsidianSyncService

**Files:**
- Create: `backend/sync/service.py`
- Create: `tests/backend/test_sync/test_service.py`

- [ ] **Step 1: Write the failing tests**

```python
import ast
import hashlib
import json
from datetime import date
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
    paper_log = [l for l in logs if l["sync_type"] == "paper_note"]
    assert len(paper_log) == 1
    assert paper_log[0]["checksum"] != ""


async def test_idempotent_sync_skips_rewrite(service, db, vault_path):
    await _setup_paper_with_analysis(db)
    await service._stage_runner.create("paper", "paper-001", "sync")

    await service.process_next()

    # Create another sync task for the same paper
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
```

- [ ] **Step 2: Write the implementation**

```python
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import date, datetime
from pathlib import Path

from backend.core.database import Database
from backend.core.stage_runner import StageRunner
from backend.sync.note_generator import generate_paper_note
from backend.sync.daily_summary import generate_daily_summary

logger = logging.getLogger(__name__)


def _sanitize_filename(title: str) -> str:
    sanitized = re.sub(r"[^\w\s-]", "", title)
    sanitized = re.sub(r"\s+", "-", sanitized.strip())
    return sanitized[:80] if sanitized else "untitled"


def _iso_week_string(d: date) -> str:
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


class ObsidianSyncService:
    def __init__(
        self,
        db: Database,
        stage_runner: StageRunner,
        vault_path: str,
        root_folder: str = "LLM-Research",
    ):
        self._db = db
        self._stage_runner = stage_runner
        self._vault_path = Path(vault_path)
        self._root_folder = root_folder

    async def process_next(self, worker_id: str = "sync-1") -> bool:
        task = await self._stage_runner.claim("sync", worker_id)
        if not task:
            return False

        try:
            paper_id = task["target_id"]

            paper = await self._db.fetch_one("SELECT * FROM papers WHERE id = ?", (paper_id,))
            if not paper:
                await self._stage_runner.fail(task["id"], f"Paper {paper_id} not found")
                return True

            pa = await self._db.fetch_one(
                "SELECT * FROM paper_analysis WHERE paper_id = ?", (paper_id,)
            )
            if not pa:
                await self._stage_runner.fail(task["id"], f"No analysis for paper {paper_id}")
                return True

            analysis = await self._db.fetch_one(
                "SELECT * FROM analysis_runs WHERE id = ?", (pa["active_analysis_run_id"],)
            )
            if not analysis:
                await self._stage_runner.fail(task["id"], f"Analysis run not found for {paper_id}")
                return True

            source = await self._db.fetch_one(
                "SELECT * FROM paper_sources WHERE paper_id = ? ORDER BY id DESC LIMIT 1",
                (paper_id,),
            )

            # Determine collected date from first_seen_at
            first_seen = paper["first_seen_at"]
            collected_date = datetime.fromisoformat(first_seen).date() if first_seen else date.today()
            week_str = _iso_week_string(collected_date)
            date_str = collected_date.isoformat()

            # Build vault directory
            day_dir = self._vault_path / self._root_folder / week_str / date_str
            day_dir.mkdir(parents=True, exist_ok=True)

            # Generate and write paper note
            note_content = generate_paper_note(dict(paper), dict(analysis), dict(source) if source else None)
            note_checksum = hashlib.sha256(note_content.encode("utf-8")).hexdigest()

            filename = _sanitize_filename(paper["title"]) + ".md"
            note_path = day_dir / filename

            existing_log = await self._db.fetch_one(
                "SELECT id FROM sync_log WHERE sync_type = 'paper_note' AND logical_target = ? AND checksum = ?",
                (f"paper:{paper_id}", note_checksum),
            )
            if not existing_log:
                note_path.write_text(note_content, encoding="utf-8")
                await self._db.execute(
                    "INSERT INTO sync_log (paper_id, sync_type, logical_target, file_path, checksum, synced_at) "
                    "VALUES (?, 'paper_note', ?, ?, ?, datetime('now'))",
                    (paper_id, f"paper:{paper_id}", str(note_path), note_checksum),
                )

            # Generate and write/update daily summary
            await self._update_daily_summary(collected_date, date_str, day_dir)

            await self._stage_runner.complete(task["id"])
            return True
        except Exception as e:
            logger.exception("Sync failed for task %s", task["id"])
            await self._stage_runner.fail(task["id"], str(e))
            return True

    async def _update_daily_summary(self, collected_date: date, date_str: str, day_dir: Path) -> None:
        # Get all papers analyzed on this date
        rows = await self._db.fetch_all(
            "SELECT p.title, ar.score_total, ar.tags, ar.factual_summary, "
            "ar.analysis_basis, ar.evidence_level "
            "FROM paper_analysis pa "
            "JOIN papers p ON pa.paper_id = p.id "
            "JOIN analysis_runs ar ON pa.active_analysis_run_id = ar.id "
            "WHERE date(p.first_seen_at) = ?",
            (date_str,),
        )
        papers_data = [dict(r) for r in rows]

        total_collected = await self._db.fetch_one(
            "SELECT COUNT(*) as cnt FROM papers WHERE date(first_seen_at) = ?",
            (date_str,),
        )
        total_analyzed = len(papers_data)

        summary_content = generate_daily_summary(
            date_str, papers_data,
            total_collected=total_collected["cnt"] if total_collected else 0,
            total_analyzed=total_analyzed,
        )
        summary_checksum = hashlib.sha256(summary_content.encode("utf-8")).hexdigest()

        summary_path = day_dir / f"{date_str}-daily.md"

        existing_log = await self._db.fetch_one(
            "SELECT id FROM sync_log WHERE sync_type = 'daily_summary' AND logical_target = ? AND checksum = ?",
            (f"daily:{date_str}", summary_checksum),
        )
        if not existing_log:
            summary_path.write_text(summary_content, encoding="utf-8")
            await self._db.execute(
                "INSERT INTO sync_log (sync_type, logical_target, file_path, checksum, synced_at) "
                "VALUES ('daily_summary', ?, ?, ?, datetime('now'))",
                (f"daily:{date_str}", str(summary_path), summary_checksum),
            )
```

- [ ] **Step 3: Run tests, lint, commit**

```bash
pytest tests/backend/test_sync/test_service.py -v
ruff check backend/sync/ tests/backend/test_sync/
git commit -m "feat: Obsidian sync service with vault writing and checksum idempotency"
```

---

### Task 4: Full Test Suite Verification

- [ ] **Step 1: Run all tests**

Run: `pytest tests/ -v`
Expected: All pass (~120 total)

- [ ] **Step 2: Run linter**

Run: `ruff check .`
Expected: All checks passed
