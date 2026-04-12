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
