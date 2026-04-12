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
