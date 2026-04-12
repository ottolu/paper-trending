from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from backend.core.embedding_client import EmbeddingClient

@pytest.fixture
def client():
    return EmbeddingClient(base_url="https://api.openai.com/v1", api_key="sk-test", model="text-embedding-3-small")

def test_client_initialization(client):
    assert client.model == "text-embedding-3-small"

async def test_embed_single_text(client):
    mock_embedding = MagicMock()
    mock_embedding.embedding = [0.1, 0.2, 0.3]
    mock_response = MagicMock()
    mock_response.data = [mock_embedding]
    with patch.object(client._client.embeddings, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        result = await client.embed(["hello world"])
        assert result == [[0.1, 0.2, 0.3]]
        mock_create.assert_called_once_with(model="text-embedding-3-small", input=["hello world"])

async def test_embed_multiple_texts(client):
    mock_emb1 = MagicMock()
    mock_emb1.embedding = [0.1, 0.2]
    mock_emb2 = MagicMock()
    mock_emb2.embedding = [0.3, 0.4]
    mock_response = MagicMock()
    mock_response.data = [mock_emb1, mock_emb2]
    with patch.object(client._client.embeddings, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        result = await client.embed(["text one", "text two"])
        assert len(result) == 2

async def test_embed_empty_list(client):
    result = await client.embed([])
    assert result == []
