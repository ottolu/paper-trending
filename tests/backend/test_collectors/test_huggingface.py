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
