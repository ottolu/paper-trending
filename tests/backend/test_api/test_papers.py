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
    # Derive a unique arxiv_id from the paper_id to avoid UNIQUE constraint violations
    arxiv_id = f"2401.{abs(hash(paper_id)) % 100000:05d}"
    await db.execute(
        "INSERT INTO papers (id, arxiv_id, title, abstract, authors, arxiv_categories, "
        "published_date, first_seen_at, updated_at) "
        "VALUES (?, ?, ?, 'Abstract text.', '[\"Author A\"]', '[\"cs.CL\"]', "
        "'2024-01-15', '2024-01-16 08:00:00', datetime('now'))",
        (paper_id, arxiv_id, title),
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
