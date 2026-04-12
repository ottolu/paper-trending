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
