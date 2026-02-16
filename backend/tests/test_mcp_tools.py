from unittest.mock import patch, AsyncMock, MagicMock, call

import pytest

from app.mcp_server.tools.web_search import search_earnings_report, _extract_text


def _make_mock_brave_client(response_data):
    mock_response = MagicMock()
    mock_response.json.return_value = response_data
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


def _make_mock_page_client():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "text/html"}
    mock_response.text = "<html><body><article><p>Company raised guidance for next quarter.</p></article></body></html>"

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestExtractText:
    def test_extracts_article_content(self):
        html = "<html><body><nav>Menu</nav><article><p>Earnings were strong.</p></article></body></html>"
        text = _extract_text(html)
        assert "Earnings were strong" in text
        assert "Menu" not in text

    def test_strips_script_and_style(self):
        html = "<html><body><script>var x=1;</script><style>.a{}</style><main><p>Content</p></main></body></html>"
        text = _extract_text(html)
        assert "Content" in text
        assert "var x" not in text


class TestSearchEarningsReport:
    @pytest.mark.asyncio
    async def test_returns_formatted_results(self, sample_brave_response):
        brave_client = _make_mock_brave_client(sample_brave_response)
        page_client = _make_mock_page_client()

        clients = [brave_client, page_client]
        with patch(
            "app.mcp_server.tools.web_search.httpx.AsyncClient",
            side_effect=lambda **kwargs: clients.pop(0) if clients else _make_mock_page_client(),
        ):
            result = await search_earnings_report("AAPL", "Q4-2025")

        assert "AAPL" in result
        assert "Q4-2025" in result
        assert "Apple Q4 2025 Earnings" in result
        assert "https://example.com/aapl-earnings" in result
        assert "Article" in result

    @pytest.mark.asyncio
    async def test_handles_no_results(self):
        brave_client = _make_mock_brave_client({"web": {"results": []}})

        with patch(
            "app.mcp_server.tools.web_search.httpx.AsyncClient",
            return_value=brave_client,
        ):
            result = await search_earnings_report("XYZ", "Q4-2025")

        assert "No search results found" in result

    @pytest.mark.asyncio
    async def test_sends_correct_headers(self, sample_brave_response):
        brave_client = _make_mock_brave_client(sample_brave_response)
        page_client = _make_mock_page_client()

        clients = [brave_client, page_client]
        with patch(
            "app.mcp_server.tools.web_search.httpx.AsyncClient",
            side_effect=lambda **kwargs: clients.pop(0) if clients else _make_mock_page_client(),
        ):
            await search_earnings_report("AAPL", "Q4-2025")

        call_args = brave_client.get.call_args
        headers = call_args.kwargs.get("headers") or call_args[1].get("headers")
        assert "X-Subscription-Token" in headers

    @pytest.mark.asyncio
    async def test_limits_to_five_results(self):
        many_results = {
            "web": {
                "results": [
                    {
                        "title": f"Result {i}",
                        "url": f"https://example.com/{i}",
                        "description": f"Description {i}",
                    }
                    for i in range(10)
                ]
            }
        }
        brave_client = _make_mock_brave_client(many_results)
        page_client = _make_mock_page_client()

        clients = [brave_client, page_client]
        with patch(
            "app.mcp_server.tools.web_search.httpx.AsyncClient",
            side_effect=lambda **kwargs: clients.pop(0) if clients else _make_mock_page_client(),
        ):
            result = await search_earnings_report("AAPL", "Q4-2025")

        assert "Result 0" in result
        assert "Result 4" in result
        assert "Result 5" not in result
