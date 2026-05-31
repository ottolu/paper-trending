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
    client.model = "test-model"
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

    # Insert directly into stage_runs to have a proper pending task with payload
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


@pytest.fixture
def mock_llm_no_total():
    """Mirrors the production v3 prompt: emits score_breakdown but NOT score_total."""
    client = AsyncMock()
    client.model = "test-model"
    client.chat_json = AsyncMock(return_value={
        "factual_summary": "S",
        "methodology_inference": "M",
        "innovation_points": ["i"],
        "key_takeaways": ["k"],
        "score_breakdown": {"novelty": 6, "rigor": 7, "impact": 7, "clarity": 8},
        "tags": ["t"],
        "evidence_level": "moderate",
        "evidence_citations": [],
        "confidence": 0.8,
    })
    return client


@pytest.fixture
def service_no_total(db, stage_runner, data_root, mock_llm_no_total, mock_embedding, mock_vector_store):
    return AnalyzerService(
        db=db,
        stage_runner=stage_runner,
        paper_root=data_root,
        llm_client=mock_llm_no_total,
        embedding_client=mock_embedding,
        vector_store=mock_vector_store,
    )


async def test_score_total_computed_as_mean_of_breakdown_when_llm_omits_it(
    service_no_total, db, data_root
):
    # v3 prompt deliberately omits score_total; Python computes it as the mean
    # of the breakdown sub-scores. mean({6,7,7,8}) == 7.0
    await _setup_paper_with_manifest(db, data_root)
    await service_no_total.process_next()

    row = await db.fetch_one(
        "SELECT score_total FROM analysis_runs WHERE paper_id = ?", ("paper-001",)
    )
    assert row["score_total"] == 7.0


async def test_records_analysis_model_and_prompt_version(service_no_total, db, data_root):
    await _setup_paper_with_manifest(db, data_root)
    await service_no_total.process_next()

    row = await db.fetch_one(
        "SELECT analysis_model, prompt_version FROM analysis_runs WHERE paper_id = ?",
        ("paper-001",),
    )
    assert row["analysis_model"] == "test-model"
    assert row["prompt_version"] == "v3"
