from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from backend.core.llm_client import LLMClient

@pytest.fixture
def client():
    return LLMClient(base_url="https://api.openai.com/v1", api_key="sk-test", model="gpt-5.4")

def test_client_initialization(client):
    assert client.model == "gpt-5.4"

async def test_chat_returns_string(client):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Hello, world!"
    with patch.object(client._client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        result = await client.chat([{"role": "user", "content": "Hi"}])
        assert result == "Hello, world!"

async def test_chat_passes_model_and_messages(client):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "response"
    with patch.object(client._client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        await client.chat([{"role": "user", "content": "test"}], temperature=0.1)
        call_kwargs = mock_create.call_args
        assert call_kwargs.kwargs["model"] == "gpt-5.4"
        assert call_kwargs.kwargs["temperature"] == 0.1

async def test_chat_json_returns_parsed_dict(client):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"score": 8.5, "tags": ["ml", "nlp"]}'
    with patch.object(client._client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        result = await client.chat_json([{"role": "user", "content": "analyze"}], response_schema={})
        assert result == {"score": 8.5, "tags": ["ml", "nlp"]}

async def test_chat_json_raises_on_invalid_json(client):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "not json"
    with patch.object(client._client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        with pytest.raises(ValueError, match="Failed to parse LLM response as JSON"):
            await client.chat_json([{"role": "user", "content": "analyze"}], response_schema={})
