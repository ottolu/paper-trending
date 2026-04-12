# Data Collection (Plan 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the arXiv and HuggingFace paper collectors that populate the `papers` and `paper_sources` tables, link multi-source records, and create downstream `pdf_fetch` stage_runs for new papers.

**Architecture:** Two source-specific fetchers (`ArxivFetcher`, `HuggingFaceFetcher`) each return a common `RawPaper` dataclass. A `PaperLinker` merges multi-source records by arXiv ID (exact) or title (fuzzy). A `CollectorService` orchestrates the full flow: fetch → link → upsert to DB → create stage_runs. All HTTP done via `httpx.AsyncClient` with configurable rate limiting.

**Tech Stack:** httpx (async HTTP), xml.etree.ElementTree (arXiv Atom parsing), difflib (fuzzy title matching), existing Database + StageRunner from Plan 1.

**Existing code context:**
- `backend/core/database.py` — `Database` class with `execute()`, `fetch_one()`, `fetch_all()`, `execute_many()`
- `backend/core/stage_runner.py` — `StageRunner` class with `create()` (idempotent via `logical_job_key`)
- `backend/core/models.py` — `Paper`, `PaperSource`, `StageStatus` Pydantic models
- `backend/config/loader.py` — `ArxivConfig` with `categories: list[str]`, `request_interval_seconds: int`
- `tests/conftest.py` — shared `test_db` async fixture (tmp_path-based SQLite)

---

## File Structure

| File | Responsibility |
|------|---------------|
| `backend/collectors/__init__.py` | Package init |
| `backend/collectors/raw_paper.py` | `RawPaper` dataclass — common format returned by all fetchers |
| `backend/collectors/arxiv.py` | `ArxivFetcher` — query arXiv API, parse Atom XML, return `list[RawPaper]` |
| `backend/collectors/huggingface.py` | `HuggingFaceFetcher` — fetch HF Daily Papers API, return `list[RawPaper]` |
| `backend/collectors/linker.py` | `PaperLinker` — merge arXiv + HF records by arXiv ID or fuzzy title |
| `backend/collectors/service.py` | `CollectorService` — orchestrate fetch → link → DB upsert → stage_run creation |
| `tests/backend/test_collectors/__init__.py` | Test package init |
| `tests/backend/test_collectors/test_raw_paper.py` | Tests for RawPaper |
| `tests/backend/test_collectors/test_arxiv.py` | Tests for ArxivFetcher (mocked HTTP) |
| `tests/backend/test_collectors/test_huggingface.py` | Tests for HuggingFaceFetcher (mocked HTTP) |
| `tests/backend/test_collectors/test_linker.py` | Tests for PaperLinker |
| `tests/backend/test_collectors/test_service.py` | Tests for CollectorService (integration with test DB) |

---

### Task 1: RawPaper Dataclass

**Files:**
- Create: `backend/collectors/__init__.py`
- Create: `backend/collectors/raw_paper.py`
- Create: `tests/backend/test_collectors/__init__.py`
- Create: `tests/backend/test_collectors/test_raw_paper.py`

- [ ] **Step 1: Write the failing test**

Create `tests/backend/test_collectors/__init__.py` (empty file) and `tests/backend/test_collectors/test_raw_paper.py`:

```python
from datetime import date

from backend.collectors.raw_paper import RawPaper


def test_raw_paper_creation_minimal():
    paper = RawPaper(
        source="arxiv",
        source_record_id="2401.00001",
        title="Test Paper",
        abstract="This is a test abstract.",
    )
    assert paper.source == "arxiv"
    assert paper.source_record_id == "2401.00001"
    assert paper.title == "Test Paper"
    assert paper.abstract == "This is a test abstract."
    assert paper.arxiv_id is None
    assert paper.authors == []
    assert paper.arxiv_categories == []
    assert paper.published_date is None
    assert paper.pdf_url is None
    assert paper.source_url is None
    assert paper.hf_likes is None
    assert paper.hf_discussions is None


def test_raw_paper_creation_full():
    paper = RawPaper(
        source="arxiv",
        source_record_id="2401.00001",
        arxiv_id="2401.00001",
        title="Full Paper",
        authors=["Author A", "Author B"],
        abstract="Full abstract.",
        arxiv_categories=["cs.CL", "cs.AI"],
        published_date=date(2024, 1, 15),
        pdf_url="https://arxiv.org/pdf/2401.00001",
        source_url="https://arxiv.org/abs/2401.00001",
    )
    assert paper.arxiv_id == "2401.00001"
    assert paper.authors == ["Author A", "Author B"]
    assert paper.arxiv_categories == ["cs.CL", "cs.AI"]
    assert paper.published_date == date(2024, 1, 15)
    assert paper.pdf_url == "https://arxiv.org/pdf/2401.00001"
    assert paper.source_url == "https://arxiv.org/abs/2401.00001"


def test_raw_paper_huggingface_source():
    paper = RawPaper(
        source="huggingface",
        source_record_id="hf-paper-123",
        title="HF Paper",
        abstract="HF abstract.",
        source_url="https://huggingface.co/papers/2401.00001",
        hf_likes=42,
        hf_discussions=5,
        arxiv_id="2401.00001",
    )
    assert paper.source == "huggingface"
    assert paper.hf_likes == 42
    assert paper.hf_discussions == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/backend/test_collectors/test_raw_paper.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'backend.collectors'"

- [ ] **Step 3: Write minimal implementation**

Create `backend/collectors/__init__.py` (empty file) and `backend/collectors/raw_paper.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class RawPaper:
    """Common format returned by all source fetchers."""

    source: str  # "arxiv" or "huggingface"
    source_record_id: str
    title: str
    abstract: str
    arxiv_id: str | None = None
    authors: list[str] = field(default_factory=list)
    arxiv_categories: list[str] = field(default_factory=list)
    published_date: date | None = None
    pdf_url: str | None = None
    source_url: str | None = None
    hf_likes: int | None = None
    hf_discussions: int | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/backend/test_collectors/test_raw_paper.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/collectors/__init__.py backend/collectors/raw_paper.py tests/backend/test_collectors/__init__.py tests/backend/test_collectors/test_raw_paper.py
git commit -m "feat: add RawPaper dataclass for collector output"
```

---

### Task 2: ArxivFetcher — XML Parsing

**Files:**
- Create: `backend/collectors/arxiv.py`
- Create: `tests/backend/test_collectors/test_arxiv.py`
- Create: `tests/backend/test_collectors/fixtures/arxiv_response.xml`

The arXiv API returns Atom XML. This task builds the parser that converts it to `RawPaper` objects. HTTP fetching is tested with mocked responses.

- [ ] **Step 1: Create the arXiv XML fixture**

Create `tests/backend/test_collectors/fixtures/arxiv_response.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
  <opensearch:totalResults>2</opensearch:totalResults>
  <opensearch:startIndex>0</opensearch:startIndex>
  <opensearch:itemsPerPage>10</opensearch:itemsPerPage>
  <entry>
    <id>http://arxiv.org/abs/2401.00001v1</id>
    <updated>2024-01-15T00:00:00Z</updated>
    <published>2024-01-15T00:00:00Z</published>
    <title>Scaling Laws for Neural Language Models</title>
    <summary>We study empirical scaling laws for language model performance.</summary>
    <author><name>Alice Smith</name></author>
    <author><name>Bob Jones</name></author>
    <arxiv:primary_category term="cs.CL"/>
    <category term="cs.CL"/>
    <category term="cs.AI"/>
    <link href="http://arxiv.org/abs/2401.00001v1" rel="alternate" type="text/html"/>
    <link href="http://arxiv.org/pdf/2401.00001v1" title="pdf" rel="related" type="application/pdf"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2401.00002v1</id>
    <updated>2024-01-15T00:00:00Z</updated>
    <published>2024-01-14T00:00:00Z</published>
    <title>Attention Is All You Need Revisited</title>
    <summary>A revisit of the transformer architecture with new insights.</summary>
    <author><name>Carol White</name></author>
    <link href="http://arxiv.org/abs/2401.00002v1" rel="alternate" type="text/html"/>
    <link href="http://arxiv.org/pdf/2401.00002v1" title="pdf" rel="related" type="application/pdf"/>
    <arxiv:primary_category term="cs.LG"/>
    <category term="cs.LG"/>
  </entry>
</feed>
```

- [ ] **Step 2: Write the failing tests**

Create `tests/backend/test_collectors/test_arxiv.py`:

```python
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from backend.collectors.arxiv import ArxivFetcher


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fetcher():
    return ArxivFetcher(
        categories=["cs.CL", "cs.AI", "cs.LG"],
        request_interval_seconds=0,
    )


@pytest.fixture
def arxiv_xml():
    return (FIXTURES_DIR / "arxiv_response.xml").read_text()


def test_parse_atom_xml(fetcher, arxiv_xml):
    papers = fetcher.parse_atom_response(arxiv_xml)
    assert len(papers) == 2

    p1 = papers[0]
    assert p1.source == "arxiv"
    assert p1.arxiv_id == "2401.00001"
    assert p1.source_record_id == "2401.00001"
    assert p1.title == "Scaling Laws for Neural Language Models"
    assert p1.abstract == "We study empirical scaling laws for language model performance."
    assert p1.authors == ["Alice Smith", "Bob Jones"]
    assert p1.arxiv_categories == ["cs.CL", "cs.AI"]
    assert p1.published_date == date(2024, 1, 15)
    assert p1.pdf_url == "http://arxiv.org/pdf/2401.00001v1"
    assert p1.source_url == "http://arxiv.org/abs/2401.00001v1"

    p2 = papers[1]
    assert p2.arxiv_id == "2401.00002"
    assert p2.authors == ["Carol White"]
    assert p2.published_date == date(2024, 1, 14)
    assert p2.arxiv_categories == ["cs.LG"]


def test_parse_empty_feed(fetcher):
    empty_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
    </feed>"""
    papers = fetcher.parse_atom_response(empty_xml)
    assert papers == []


def test_extract_arxiv_id_from_url(fetcher):
    assert fetcher._extract_arxiv_id("http://arxiv.org/abs/2401.00001v1") == "2401.00001"
    assert fetcher._extract_arxiv_id("http://arxiv.org/abs/2401.00001v2") == "2401.00001"
    assert fetcher._extract_arxiv_id("http://arxiv.org/abs/cs/0601001v1") == "cs/0601001"


async def test_fetch_papers_calls_api(fetcher, arxiv_xml):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = arxiv_xml
    mock_response.raise_for_status = MagicMock()

    with patch("backend.collectors.arxiv.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        papers = await fetcher.fetch(date_from=date(2024, 1, 14), date_to=date(2024, 1, 15))

    assert len(papers) == 2
    mock_client.get.assert_called_once()
    call_args = mock_client.get.call_args
    assert "export.arxiv.org" in call_args[0][0]


async def test_fetch_papers_retries_on_503(fetcher):
    error_response = MagicMock()
    error_response.status_code = 503
    error_response.raise_for_status = MagicMock(side_effect=Exception("503 Service Unavailable"))

    ok_response = MagicMock()
    ok_response.status_code = 200
    ok_response.text = '<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
    ok_response.raise_for_status = MagicMock()

    with patch("backend.collectors.arxiv.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=[error_response, ok_response])

        papers = await fetcher.fetch(date_from=date(2024, 1, 14), date_to=date(2024, 1, 15))

    assert papers == []
    assert mock_client.get.call_count == 2
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/backend/test_collectors/test_arxiv.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'backend.collectors.arxiv'"

- [ ] **Step 4: Write the implementation**

Create `backend/collectors/arxiv.py`:

```python
from __future__ import annotations

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from datetime import date

import httpx

from backend.collectors.raw_paper import RawPaper

logger = logging.getLogger(__name__)

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM_NS = "http://www.w3.org/2005/Atom"
ARXIV_NS = "http://arxiv.org/schemas/atom"

_ARXIV_ID_RE = re.compile(r"arxiv\.org/abs/(.+?)(?:v\d+)?$")


class ArxivFetcher:
    def __init__(self, categories: list[str], request_interval_seconds: int = 3):
        self._categories = categories
        self._interval = request_interval_seconds

    async def fetch(
        self,
        date_from: date,
        date_to: date,
        max_results: int = 500,
    ) -> list[RawPaper]:
        cat_query = " OR ".join(f"cat:{c}" for c in self._categories)
        date_range = (
            f"submittedDate:[{date_from.strftime('%Y%m%d')}0000 TO {date_to.strftime('%Y%m%d')}2359]"
        )
        search_query = f"({cat_query}) AND {date_range}"

        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(ARXIV_API_URL, params=params)
                    if response.status_code == 503:
                        raise httpx.HTTPStatusError(
                            "503", request=response.request, response=response
                        )
                    response.raise_for_status()
                    return self.parse_atom_response(response.text)
            except Exception:
                wait = 3 ** (attempt + 1)
                logger.warning("arXiv request failed (attempt %d/3), retrying in %ds", attempt + 1, wait)
                if attempt < 2:
                    await asyncio.sleep(wait)
        return []

    def parse_atom_response(self, xml_text: str) -> list[RawPaper]:
        root = ET.fromstring(xml_text)
        papers: list[RawPaper] = []

        for entry in root.findall(f"{{{ATOM_NS}}}entry"):
            id_elem = entry.find(f"{{{ATOM_NS}}}id")
            if id_elem is None or id_elem.text is None:
                continue

            arxiv_id = self._extract_arxiv_id(id_elem.text)
            title_elem = entry.find(f"{{{ATOM_NS}}}title")
            summary_elem = entry.find(f"{{{ATOM_NS}}}summary")
            published_elem = entry.find(f"{{{ATOM_NS}}}published")

            title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
            abstract = summary_elem.text.strip() if summary_elem is not None and summary_elem.text else ""

            authors = []
            for author_elem in entry.findall(f"{{{ATOM_NS}}}author"):
                name_elem = author_elem.find(f"{{{ATOM_NS}}}name")
                if name_elem is not None and name_elem.text:
                    authors.append(name_elem.text)

            categories = []
            for cat_elem in entry.findall(f"{{{ATOM_NS}}}category"):
                term = cat_elem.get("term")
                if term:
                    categories.append(term)

            published_date_val = None
            if published_elem is not None and published_elem.text:
                published_date_val = date.fromisoformat(published_elem.text[:10])

            pdf_url = None
            source_url = None
            for link in entry.findall(f"{{{ATOM_NS}}}link"):
                if link.get("title") == "pdf":
                    pdf_url = link.get("href")
                elif link.get("rel") == "alternate":
                    source_url = link.get("href")

            papers.append(
                RawPaper(
                    source="arxiv",
                    source_record_id=arxiv_id or "",
                    arxiv_id=arxiv_id,
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    arxiv_categories=categories,
                    published_date=published_date_val,
                    pdf_url=pdf_url,
                    source_url=source_url,
                )
            )

        return papers

    @staticmethod
    def _extract_arxiv_id(url: str) -> str | None:
        match = _ARXIV_ID_RE.search(url)
        return match.group(1) if match else None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/backend/test_collectors/test_arxiv.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add backend/collectors/arxiv.py tests/backend/test_collectors/test_arxiv.py tests/backend/test_collectors/fixtures/arxiv_response.xml
git commit -m "feat: arXiv fetcher with Atom XML parsing and retry"
```

---

### Task 3: HuggingFaceFetcher

**Files:**
- Create: `backend/collectors/huggingface.py`
- Create: `tests/backend/test_collectors/test_huggingface.py`

HuggingFace Daily Papers API returns JSON. The fetcher extracts paper metadata and HF-specific signals (likes, discussions).

- [ ] **Step 1: Write the failing tests**

Create `tests/backend/test_collectors/test_huggingface.py`:

```python
from datetime import date
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from backend.collectors.huggingface import HuggingFaceFetcher


@pytest.fixture
def fetcher():
    return HuggingFaceFetcher(request_interval_seconds=0)


@pytest.fixture
def hf_api_response():
    return [
        {
            "paper": {
                "id": "2401.00001",
                "title": "Scaling Laws for Neural Language Models",
                "summary": "We study empirical scaling laws.",
                "authors": [{"name": "Alice Smith"}, {"name": "Bob Jones"}],
                "publishedAt": "2024-01-15T00:00:00.000Z",
            },
            "numLikes": 42,
            "numComments": 5,
        },
        {
            "paper": {
                "id": "2401.00099",
                "title": "New Approach to RLHF",
                "summary": "We propose a new alignment method.",
                "authors": [{"name": "Eve Black"}],
                "publishedAt": "2024-01-15T00:00:00.000Z",
            },
            "numLikes": 10,
            "numComments": 2,
        },
    ]


def test_parse_daily_papers(fetcher, hf_api_response):
    papers = fetcher.parse_response(hf_api_response)
    assert len(papers) == 2

    p1 = papers[0]
    assert p1.source == "huggingface"
    assert p1.source_record_id == "2401.00001"
    assert p1.arxiv_id == "2401.00001"
    assert p1.title == "Scaling Laws for Neural Language Models"
    assert p1.abstract == "We study empirical scaling laws."
    assert p1.authors == ["Alice Smith", "Bob Jones"]
    assert p1.hf_likes == 42
    assert p1.hf_discussions == 5
    assert p1.source_url == "https://huggingface.co/papers/2401.00001"

    p2 = papers[1]
    assert p2.arxiv_id == "2401.00099"
    assert p2.hf_likes == 10


def test_parse_empty_response(fetcher):
    papers = fetcher.parse_response([])
    assert papers == []


def test_parse_missing_optional_fields(fetcher):
    response = [
        {
            "paper": {
                "id": "2401.00003",
                "title": "Minimal Paper",
                "summary": "Short.",
            },
            "numLikes": 0,
            "numComments": 0,
        },
    ]
    papers = fetcher.parse_response(response)
    assert len(papers) == 1
    assert papers[0].authors == []
    assert papers[0].published_date is None


async def test_fetch_calls_api(fetcher, hf_api_response):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = hf_api_response
    mock_response.raise_for_status = MagicMock()

    with patch("backend.collectors.huggingface.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        papers = await fetcher.fetch(target_date=date(2024, 1, 15))

    assert len(papers) == 2
    mock_client.get.assert_called_once()
    call_url = mock_client.get.call_args[0][0]
    assert "huggingface.co" in call_url
    assert "2024-01-15" in call_url


async def test_fetch_retries_on_failure(fetcher):
    error_response = MagicMock()
    error_response.status_code = 500
    error_response.raise_for_status = MagicMock(side_effect=Exception("500 Server Error"))

    ok_response = MagicMock()
    ok_response.status_code = 200
    ok_response.json.return_value = []
    ok_response.raise_for_status = MagicMock()

    with patch("backend.collectors.huggingface.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=[error_response, ok_response])

        papers = await fetcher.fetch(target_date=date(2024, 1, 15))

    assert papers == []
    assert mock_client.get.call_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/backend/test_collectors/test_huggingface.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'backend.collectors.huggingface'"

- [ ] **Step 3: Write the implementation**

Create `backend/collectors/huggingface.py`:

```python
from __future__ import annotations

import asyncio
import logging
from datetime import date

import httpx

from backend.collectors.raw_paper import RawPaper

logger = logging.getLogger(__name__)

HF_DAILY_PAPERS_URL = "https://huggingface.co/api/daily_papers"


class HuggingFaceFetcher:
    def __init__(self, request_interval_seconds: int = 3):
        self._interval = request_interval_seconds

    async def fetch(self, target_date: date) -> list[RawPaper]:
        url = f"{HF_DAILY_PAPERS_URL}?date={target_date.isoformat()}"

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url)
                    if response.status_code >= 500:
                        raise httpx.HTTPStatusError(
                            f"{response.status_code}", request=response.request, response=response
                        )
                    response.raise_for_status()
                    return self.parse_response(response.json())
            except Exception:
                wait = 3 ** (attempt + 1)
                logger.warning(
                    "HuggingFace request failed (attempt %d/3), retrying in %ds",
                    attempt + 1,
                    wait,
                )
                if attempt < 2:
                    await asyncio.sleep(wait)
        return []

    def parse_response(self, data: list[dict]) -> list[RawPaper]:
        papers: list[RawPaper] = []

        for item in data:
            paper_data = item.get("paper", {})
            paper_id = paper_data.get("id", "")

            authors = []
            for author in paper_data.get("authors", []):
                name = author.get("name")
                if name:
                    authors.append(name)

            published_date_val = None
            published_str = paper_data.get("publishedAt")
            if published_str:
                try:
                    published_date_val = date.fromisoformat(published_str[:10])
                except ValueError:
                    pass

            papers.append(
                RawPaper(
                    source="huggingface",
                    source_record_id=paper_id,
                    arxiv_id=paper_id if paper_id else None,
                    title=paper_data.get("title", ""),
                    authors=authors,
                    abstract=paper_data.get("summary", ""),
                    published_date=published_date_val,
                    source_url=f"https://huggingface.co/papers/{paper_id}" if paper_id else None,
                    hf_likes=item.get("numLikes"),
                    hf_discussions=item.get("numComments"),
                )
            )

        return papers
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/backend/test_collectors/test_huggingface.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend/collectors/huggingface.py tests/backend/test_collectors/test_huggingface.py
git commit -m "feat: HuggingFace fetcher with Daily Papers API parsing"
```

---

### Task 4: PaperLinker

**Files:**
- Create: `backend/collectors/linker.py`
- Create: `tests/backend/test_collectors/test_linker.py`

Links arXiv and HuggingFace records by arXiv ID (exact match) or fuzzy title matching. Outputs a merged list of `LinkedPaper` objects that carry data from both sources.

- [ ] **Step 1: Write the failing tests**

Create `tests/backend/test_collectors/test_linker.py`:

```python
from datetime import date

from backend.collectors.linker import PaperLinker, LinkedPaper
from backend.collectors.raw_paper import RawPaper


def _arxiv_paper(arxiv_id: str, title: str) -> RawPaper:
    return RawPaper(
        source="arxiv",
        source_record_id=arxiv_id,
        arxiv_id=arxiv_id,
        title=title,
        abstract=f"Abstract for {title}",
        authors=["Author A"],
        arxiv_categories=["cs.CL"],
        published_date=date(2024, 1, 15),
        pdf_url=f"http://arxiv.org/pdf/{arxiv_id}",
        source_url=f"http://arxiv.org/abs/{arxiv_id}",
    )


def _hf_paper(arxiv_id: str, title: str, likes: int = 10) -> RawPaper:
    return RawPaper(
        source="huggingface",
        source_record_id=arxiv_id,
        arxiv_id=arxiv_id,
        title=title,
        abstract=f"Abstract for {title}",
        source_url=f"https://huggingface.co/papers/{arxiv_id}",
        hf_likes=likes,
        hf_discussions=2,
    )


def test_link_by_arxiv_id():
    linker = PaperLinker()
    arxiv_papers = [_arxiv_paper("2401.00001", "Paper One")]
    hf_papers = [_hf_paper("2401.00001", "Paper One", likes=42)]

    linked = linker.link(arxiv_papers, hf_papers)

    assert len(linked) == 1
    lp = linked[0]
    assert lp.paper_id == "2401.00001"
    assert lp.arxiv_source is not None
    assert lp.hf_source is not None
    assert lp.match_strategy == "arxiv_id"
    assert lp.match_confidence == 1.0


def test_unmatched_papers_preserved():
    linker = PaperLinker()
    arxiv_papers = [_arxiv_paper("2401.00001", "Paper One")]
    hf_papers = [_hf_paper("2401.99999", "Totally Different Paper")]

    linked = linker.link(arxiv_papers, hf_papers)

    assert len(linked) == 2
    arxiv_only = [lp for lp in linked if lp.hf_source is None]
    hf_only = [lp for lp in linked if lp.arxiv_source is None]
    assert len(arxiv_only) == 1
    assert len(hf_only) == 1


def test_fuzzy_title_match():
    linker = PaperLinker(fuzzy_threshold=0.85)
    arxiv_papers = [_arxiv_paper("2401.00001", "Scaling Laws for Neural Language Models")]
    hf_papers = [
        RawPaper(
            source="huggingface",
            source_record_id="hf-unknown",
            arxiv_id=None,
            title="Scaling Laws for Neural Language Model",
            abstract="Close title match.",
            hf_likes=5,
            hf_discussions=1,
        ),
    ]

    linked = linker.link(arxiv_papers, hf_papers)

    assert len(linked) == 1
    assert linked[0].match_strategy == "fuzzy_title"
    assert linked[0].match_confidence is not None
    assert linked[0].match_confidence >= 0.85


def test_fuzzy_match_below_threshold_not_linked():
    linker = PaperLinker(fuzzy_threshold=0.85)
    arxiv_papers = [_arxiv_paper("2401.00001", "Scaling Laws for Neural Language Models")]
    hf_papers = [
        RawPaper(
            source="huggingface",
            source_record_id="hf-unknown",
            arxiv_id=None,
            title="Completely Unrelated Title About Robots",
            abstract="No match.",
            hf_likes=5,
            hf_discussions=1,
        ),
    ]

    linked = linker.link(arxiv_papers, hf_papers)

    assert len(linked) == 2


def test_linked_paper_primary_fields():
    linker = PaperLinker()
    arxiv_papers = [_arxiv_paper("2401.00001", "Paper One")]
    hf_papers = [_hf_paper("2401.00001", "Paper One", likes=42)]

    linked = linker.link(arxiv_papers, hf_papers)

    lp = linked[0]
    assert lp.title == "Paper One"
    assert lp.abstract == "Abstract for Paper One"
    assert lp.authors == ["Author A"]
    assert lp.arxiv_categories == ["cs.CL"]
    assert lp.published_date == date(2024, 1, 15)
    assert lp.pdf_url == "http://arxiv.org/pdf/2401.00001"


def test_empty_inputs():
    linker = PaperLinker()
    assert linker.link([], []) == []
    assert len(linker.link([_arxiv_paper("2401.00001", "P1")], [])) == 1
    assert len(linker.link([], [_hf_paper("2401.00001", "P1")])) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/backend/test_collectors/test_linker.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'backend.collectors.linker'"

- [ ] **Step 3: Write the implementation**

Create `backend/collectors/linker.py`:

```python
from __future__ import annotations

import difflib
from dataclasses import dataclass
from datetime import date

from backend.collectors.raw_paper import RawPaper


@dataclass
class LinkedPaper:
    """A paper with merged data from arXiv and/or HuggingFace sources."""

    paper_id: str
    title: str
    authors: list[str]
    abstract: str
    arxiv_id: str | None
    arxiv_categories: list[str]
    published_date: date | None
    pdf_url: str | None
    arxiv_source: RawPaper | None
    hf_source: RawPaper | None
    match_strategy: str  # "arxiv_id", "fuzzy_title", or "none"
    match_confidence: float | None


class PaperLinker:
    def __init__(self, fuzzy_threshold: float = 0.85):
        self._fuzzy_threshold = fuzzy_threshold

    def link(
        self,
        arxiv_papers: list[RawPaper],
        hf_papers: list[RawPaper],
    ) -> list[LinkedPaper]:
        results: list[LinkedPaper] = []
        hf_by_arxiv_id: dict[str, RawPaper] = {}
        hf_unmatched: list[RawPaper] = []

        for hf in hf_papers:
            if hf.arxiv_id:
                hf_by_arxiv_id[hf.arxiv_id] = hf
            else:
                hf_unmatched.append(hf)

        matched_hf_ids: set[str] = set()

        for arxiv in arxiv_papers:
            hf_match: RawPaper | None = None
            strategy = "none"
            confidence: float | None = None

            if arxiv.arxiv_id and arxiv.arxiv_id in hf_by_arxiv_id:
                hf_match = hf_by_arxiv_id[arxiv.arxiv_id]
                strategy = "arxiv_id"
                confidence = 1.0
                matched_hf_ids.add(arxiv.arxiv_id)
            else:
                best_ratio = 0.0
                best_hf: RawPaper | None = None
                for hf in hf_unmatched:
                    ratio = difflib.SequenceMatcher(
                        None,
                        arxiv.title.lower(),
                        hf.title.lower(),
                    ).ratio()
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_hf = hf
                if best_hf and best_ratio >= self._fuzzy_threshold:
                    hf_match = best_hf
                    strategy = "fuzzy_title"
                    confidence = best_ratio
                    hf_unmatched.remove(best_hf)

            results.append(
                LinkedPaper(
                    paper_id=arxiv.arxiv_id or arxiv.source_record_id,
                    title=arxiv.title,
                    authors=arxiv.authors,
                    abstract=arxiv.abstract,
                    arxiv_id=arxiv.arxiv_id,
                    arxiv_categories=arxiv.arxiv_categories,
                    published_date=arxiv.published_date,
                    pdf_url=arxiv.pdf_url,
                    arxiv_source=arxiv,
                    hf_source=hf_match,
                    match_strategy=strategy,
                    match_confidence=confidence,
                )
            )

        for hf_id, hf in hf_by_arxiv_id.items():
            if hf_id not in matched_hf_ids:
                results.append(
                    LinkedPaper(
                        paper_id=hf.arxiv_id or hf.source_record_id,
                        title=hf.title,
                        authors=hf.authors,
                        abstract=hf.abstract,
                        arxiv_id=hf.arxiv_id,
                        arxiv_categories=[],
                        published_date=hf.published_date,
                        pdf_url=None,
                        arxiv_source=None,
                        hf_source=hf,
                        match_strategy="none",
                        match_confidence=None,
                    )
                )

        for hf in hf_unmatched:
            results.append(
                LinkedPaper(
                    paper_id=hf.arxiv_id or hf.source_record_id,
                    title=hf.title,
                    authors=hf.authors,
                    abstract=hf.abstract,
                    arxiv_id=hf.arxiv_id,
                    arxiv_categories=[],
                    published_date=hf.published_date,
                    pdf_url=None,
                    arxiv_source=None,
                    hf_source=hf,
                    match_strategy="none",
                    match_confidence=None,
                )
            )

        return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/backend/test_collectors/test_linker.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add backend/collectors/linker.py tests/backend/test_collectors/test_linker.py
git commit -m "feat: paper linker with arXiv ID and fuzzy title matching"
```

---

### Task 5: CollectorService — DB Upsert Logic

**Files:**
- Create: `backend/collectors/service.py`
- Create: `tests/backend/test_collectors/test_service.py`

The CollectorService orchestrates: fetch from both sources → link → upsert to `papers` + `paper_sources` → create `pdf_fetch` stage_runs for new papers. This task focuses on the DB upsert and stage_run creation logic (tested with a real SQLite DB). Fetching is mocked.

- [ ] **Step 1: Write the failing tests**

Create `tests/backend/test_collectors/test_service.py`:

```python
import json
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from backend.collectors.linker import LinkedPaper
from backend.collectors.raw_paper import RawPaper
from backend.collectors.service import CollectorService
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
def service(db, stage_runner):
    return CollectorService(db=db, stage_runner=stage_runner)


def _make_linked_paper(
    arxiv_id: str,
    title: str = "Test Paper",
    has_hf: bool = False,
) -> LinkedPaper:
    arxiv_raw = RawPaper(
        source="arxiv",
        source_record_id=arxiv_id,
        arxiv_id=arxiv_id,
        title=title,
        authors=["Author A"],
        abstract=f"Abstract for {title}",
        arxiv_categories=["cs.CL"],
        published_date=date(2024, 1, 15),
        pdf_url=f"http://arxiv.org/pdf/{arxiv_id}",
        source_url=f"http://arxiv.org/abs/{arxiv_id}",
    )
    hf_raw = None
    if has_hf:
        hf_raw = RawPaper(
            source="huggingface",
            source_record_id=arxiv_id,
            arxiv_id=arxiv_id,
            title=title,
            abstract=f"Abstract for {title}",
            source_url=f"https://huggingface.co/papers/{arxiv_id}",
            hf_likes=42,
            hf_discussions=5,
        )
    return LinkedPaper(
        paper_id=arxiv_id,
        title=title,
        authors=["Author A"],
        abstract=f"Abstract for {title}",
        arxiv_id=arxiv_id,
        arxiv_categories=["cs.CL"],
        published_date=date(2024, 1, 15),
        pdf_url=f"http://arxiv.org/pdf/{arxiv_id}",
        arxiv_source=arxiv_raw,
        hf_source=hf_raw,
        match_strategy="arxiv_id" if has_hf else "none",
        match_confidence=1.0 if has_hf else None,
    )


async def test_upsert_paper_creates_new_record(service, db):
    lp = _make_linked_paper("2401.00001", "Test Paper")
    await service.upsert_paper(lp)

    row = await db.fetch_one("SELECT * FROM papers WHERE id = ?", ("2401.00001",))
    assert row is not None
    assert row["title"] == "Test Paper"
    assert row["arxiv_id"] == "2401.00001"
    assert row["abstract"] == "Abstract for Test Paper"


async def test_upsert_paper_is_idempotent(service, db):
    lp = _make_linked_paper("2401.00001", "Test Paper")
    await service.upsert_paper(lp)
    await service.upsert_paper(lp)

    rows = await db.fetch_all("SELECT * FROM papers WHERE id = ?", ("2401.00001",))
    assert len(rows) == 1


async def test_upsert_creates_arxiv_source(service, db):
    lp = _make_linked_paper("2401.00001", "Test Paper")
    await service.upsert_paper(lp)

    sources = await db.fetch_all(
        "SELECT * FROM paper_sources WHERE paper_id = ?", ("2401.00001",)
    )
    assert len(sources) == 1
    assert sources[0]["source_name"] == "arxiv"
    assert sources[0]["match_strategy"] == "arxiv_id"


async def test_upsert_creates_hf_source(service, db):
    lp = _make_linked_paper("2401.00001", "Test Paper", has_hf=True)
    await service.upsert_paper(lp)

    sources = await db.fetch_all(
        "SELECT * FROM paper_sources WHERE paper_id = ?", ("2401.00001",)
    )
    assert len(sources) == 2
    source_names = {s["source_name"] for s in sources}
    assert source_names == {"arxiv", "huggingface"}

    hf_source = next(s for s in sources if s["source_name"] == "huggingface")
    assert hf_source["hf_likes"] == 42
    assert hf_source["hf_discussions"] == 5


async def test_upsert_creates_pdf_fetch_stage_run(service, db, stage_runner):
    lp = _make_linked_paper("2401.00001", "Test Paper")
    await service.upsert_paper(lp)

    runs = await stage_runner.list_by_status("pdf_fetch", "pending")
    assert len(runs) == 1
    assert runs[0]["target_id"] == "2401.00001"


async def test_upsert_does_not_duplicate_stage_run(service, db, stage_runner):
    lp = _make_linked_paper("2401.00001", "Test Paper")
    await service.upsert_paper(lp)
    await service.upsert_paper(lp)

    runs = await stage_runner.list_by_status("pdf_fetch", "pending")
    assert len(runs) == 1


async def test_collect_orchestrates_full_flow(service, db):
    lp1 = _make_linked_paper("2401.00001", "Paper One", has_hf=True)
    lp2 = _make_linked_paper("2401.00002", "Paper Two")

    with (
        patch.object(service, "_fetch_arxiv", new_callable=AsyncMock) as mock_arxiv,
        patch.object(service, "_fetch_hf", new_callable=AsyncMock) as mock_hf,
        patch.object(service._linker, "link", return_value=[lp1, lp2]),
    ):
        mock_arxiv.return_value = [lp1.arxiv_source, lp2.arxiv_source]
        mock_hf.return_value = [lp1.hf_source]

        result = await service.collect(date_from=date(2024, 1, 14), date_to=date(2024, 1, 15))

    assert result["papers_upserted"] == 2
    assert result["sources_created"] >= 3

    papers = await db.fetch_all("SELECT * FROM papers")
    assert len(papers) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/backend/test_collectors/test_service.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'backend.collectors.service'"

- [ ] **Step 3: Write the implementation**

Create `backend/collectors/service.py`:

```python
from __future__ import annotations

import json
import logging
from datetime import date

from backend.collectors.arxiv import ArxivFetcher
from backend.collectors.huggingface import HuggingFaceFetcher
from backend.collectors.linker import LinkedPaper, PaperLinker
from backend.collectors.raw_paper import RawPaper
from backend.core.database import Database
from backend.core.stage_runner import StageRunner

logger = logging.getLogger(__name__)


class CollectorService:
    def __init__(
        self,
        db: Database,
        stage_runner: StageRunner,
        arxiv_categories: list[str] | None = None,
        arxiv_interval: int = 3,
        hf_interval: int = 3,
        fuzzy_threshold: float = 0.85,
    ):
        self._db = db
        self._stage_runner = stage_runner
        self._arxiv_fetcher = ArxivFetcher(
            categories=arxiv_categories or ["cs.CL", "cs.AI", "cs.LG"],
            request_interval_seconds=arxiv_interval,
        )
        self._hf_fetcher = HuggingFaceFetcher(request_interval_seconds=hf_interval)
        self._linker = PaperLinker(fuzzy_threshold=fuzzy_threshold)

    async def collect(
        self,
        date_from: date,
        date_to: date,
    ) -> dict:
        arxiv_papers = await self._fetch_arxiv(date_from, date_to)
        hf_papers = await self._fetch_hf(date_to)
        linked = self._linker.link(arxiv_papers, hf_papers)

        papers_upserted = 0
        sources_created = 0

        for lp in linked:
            result = await self.upsert_paper(lp)
            papers_upserted += 1
            sources_created += result["sources_created"]

        logger.info(
            "Collection complete: %d papers upserted, %d sources created",
            papers_upserted,
            sources_created,
        )

        return {
            "papers_upserted": papers_upserted,
            "sources_created": sources_created,
        }

    async def upsert_paper(self, lp: LinkedPaper) -> dict:
        existing = await self._db.fetch_one(
            "SELECT id FROM papers WHERE id = ?", (lp.paper_id,)
        )

        if existing:
            await self._db.execute(
                "UPDATE papers SET title = ?, authors = ?, abstract = ?, "
                "arxiv_categories = ?, published_date = ?, updated_at = datetime('now') "
                "WHERE id = ?",
                (
                    lp.title,
                    json.dumps(lp.authors),
                    lp.abstract,
                    json.dumps(lp.arxiv_categories),
                    lp.published_date.isoformat() if lp.published_date else None,
                    lp.paper_id,
                ),
            )
        else:
            await self._db.execute(
                "INSERT INTO papers (id, arxiv_id, title, authors, abstract, arxiv_categories, "
                "published_date, first_seen_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))",
                (
                    lp.paper_id,
                    lp.arxiv_id,
                    lp.title,
                    json.dumps(lp.authors),
                    lp.abstract,
                    json.dumps(lp.arxiv_categories),
                    lp.published_date.isoformat() if lp.published_date else None,
                ),
            )

        sources_created = 0

        if lp.arxiv_source:
            sources_created += await self._upsert_source(lp.paper_id, lp.arxiv_source, lp)

        if lp.hf_source:
            sources_created += await self._upsert_source(lp.paper_id, lp.hf_source, lp)

        if lp.pdf_url:
            await self._stage_runner.create(
                target_type="paper",
                target_id=lp.paper_id,
                stage="pdf_fetch",
                payload={"pdf_url": lp.pdf_url},
            )

        return {"sources_created": sources_created}

    async def _upsert_source(
        self,
        paper_id: str,
        raw: RawPaper,
        lp: LinkedPaper,
    ) -> int:
        existing = await self._db.fetch_one(
            "SELECT id FROM paper_sources WHERE paper_id = ? AND source_name = ?",
            (paper_id, raw.source),
        )
        if existing:
            return 0

        await self._db.execute(
            "INSERT INTO paper_sources (paper_id, source_name, source_url, source_record_id, "
            "match_strategy, match_confidence, hf_likes, hf_discussions, collected_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
            (
                paper_id,
                raw.source,
                raw.source_url,
                raw.source_record_id,
                lp.match_strategy if raw.source != "arxiv" else "arxiv_id",
                lp.match_confidence if raw.source != "arxiv" else 1.0,
                raw.hf_likes,
                raw.hf_discussions,
            ),
        )
        return 1

    async def _fetch_arxiv(self, date_from: date, date_to: date) -> list[RawPaper]:
        return await self._arxiv_fetcher.fetch(date_from=date_from, date_to=date_to)

    async def _fetch_hf(self, target_date: date) -> list[RawPaper]:
        return await self._hf_fetcher.fetch(target_date=target_date)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/backend/test_collectors/test_service.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add backend/collectors/service.py tests/backend/test_collectors/test_service.py
git commit -m "feat: collector service with DB upsert and stage_run creation"
```

---

### Task 6: Full Test Suite Verification and Lint

**Files:**
- Modify: any files with lint issues

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -v`
Expected: All tests pass (52 existing + ~28 new = ~80 total)

- [ ] **Step 2: Run linter**

Run: `ruff check .`
Expected: All checks passed

If there are lint issues, fix them (expand inline statements to multi-line, remove unused imports, etc.).

- [ ] **Step 3: Run tests one more time after any lint fixes**

Run: `pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 4: Commit if any lint fixes were needed**

```bash
git add -u
git commit -m "chore: fix lint errors, plan 2 data collection complete"
```
