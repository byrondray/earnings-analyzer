from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from app.mcp_server.tools.web_search import search_earnings_report


class TestSearchEarningsReport:
    @pytest.mark.asyncio
    async def test_returns_formatted_results(self, sample_brave_response):
        mock_response = AsyncMock()
        mock_response.json.return_value = sample_brave_response
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.mcp_server.tools.web_search.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await search_earnings_report("AAPL", "Q4-2025")

        assert "AAPL" in result
        assert "Q4-2025" in result
        assert "Apple Q4 2025 Earnings" in result
        assert "https://example.com/aapl-earnings" in result

    @pytest.mark.asyncio
    async def test_handles_no_results(self):
        mock_response = AsyncMock()
        mock_response.json.return_value = {"web": {"results": []}}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.mcp_server.tools.web_search.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await search_earnings_report("XYZ", "Q4-2025")

        assert "No search results found" in result

    @pytest.mark.asyncio
    async def test_sends_correct_headers(self, sample_brave_response):
        mock_response = AsyncMock()
        mock_response.json.return_value = sample_brave_response
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.mcp_server.tools.web_search.httpx.AsyncClient",
            return_value=mock_client,
        ):
            await search_earnings_report("AAPL", "Q4-2025")

        call_args = mock_client.get.call_args
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
        mock_response = AsyncMock()
        mock_response.json.return_value = many_results
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.mcp_server.tools.web_search.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await search_earnings_report("AAPL", "Q4-2025")

        assert "Result 0" in result
        assert "Result 4" in result
        assert "Result 5" not in result
