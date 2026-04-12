import numpy as np
import pytest

from backend.core.database import Database
from backend.reporter.cluster import ClusterService


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.initialize()
    # Insert prerequisite embedding_versions row (FK from cluster_runs)
    await database.execute(
        "INSERT INTO embedding_versions (id, provider, model, dimension, collection_name, "
        "is_active, created_at) VALUES (1, 'openai', 'text-embedding-3-small', 8, 'test', 1, "
        "datetime('now'))"
    )
    yield database
    await database.close()


def _make_embeddings(
    n: int, dim: int = 8, n_clusters: int = 2
) -> tuple[list[str], list[list[float]]]:
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


async def _insert_papers(db: Database, paper_ids: list[str]) -> None:
    """Insert paper rows to satisfy FK constraint on paper_cluster_assignments."""
    for i, paper_id in enumerate(paper_ids):
        await db.execute(
            "INSERT OR IGNORE INTO papers (id, title, abstract, first_seen_at, updated_at) "
            "VALUES (?, ?, ?, datetime('now'), datetime('now'))",
            (paper_id, f"Paper {i}", "Abstract"),
        )


async def test_run_cluster_creates_cluster_run(db):
    svc = ClusterService(db)
    ids, embeddings = _make_embeddings(20, dim=8, n_clusters=2)
    await _insert_papers(db, ids)

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
    await _insert_papers(db, ids)

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
    await _insert_papers(db, ids)

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
    await _insert_papers(db, ids)

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
