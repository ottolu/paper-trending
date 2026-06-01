from __future__ import annotations

import datetime as _dt

import pytest

from backend.collectors.service import CollectorService
from backend.core.database import Database
from backend.core.stage_runner import StageRunner


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.initialize()
    yield database
    await database.close()


_FAKE_API = [
    {
        "paper": {
            "id": "2401.00001", "title": "A", "summary": "x",
            "authors": [{"name": "Z"}], "publishedAt": "2024-01-15T00:00:00.000Z",
            "upvotes": 99,
        },
        "numComments": 1,
    },
    {
        "paper": {
            "id": "2401.00002", "title": "B", "summary": "y",
            "authors": [], "publishedAt": "2024-01-15T00:00:00.000Z",
            "upvotes": 5,
        },
        "numComments": 0,
    },
]


def _patch_fetch(monkeypatch, svc):
    async def fake_fetch(target_date):
        return svc._hf_fetcher.parse_response(_FAKE_API)
    monkeypatch.setattr(svc._hf_fetcher, "fetch", fake_fetch)


async def test_collect_hf_daily_ingests_top_n_by_upvotes(db, monkeypatch):
    sr = StageRunner(db)
    svc = CollectorService(db, sr)
    _patch_fetch(monkeypatch, svc)

    res = await svc.collect_hf_daily(target_date=_dt.date(2024, 1, 15), top=1)

    assert res["new"] == 1  # only the top-1 by upvotes
    rows = await db.fetch_all("SELECT id FROM papers")
    assert [r["id"] for r in rows] == ["2401.00001"]  # the 99-upvote paper
    pending = await sr.list_by_status("pdf_fetch", "pending")
    assert len(pending) == 1


async def test_collect_hf_daily_skips_existing_no_requeue(db, monkeypatch):
    sr = StageRunner(db)
    svc = CollectorService(db, sr)
    _patch_fetch(monkeypatch, svc)

    first = await svc.collect_hf_daily(target_date=_dt.date(2024, 1, 15), top=15)
    assert first["new"] == 2 and first["skipped"] == 0

    second = await svc.collect_hf_daily(target_date=_dt.date(2024, 1, 15), top=15)
    assert second["new"] == 0 and second["skipped"] == 2

    pending = await sr.list_by_status("pdf_fetch", "pending")
    assert len(pending) == 2  # NOT re-queued on the second run
