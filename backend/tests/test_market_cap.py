from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.services.market_cap import (
    fetch_market_cap,
    fetch_market_caps_batch,
    _fetch_market_cap_from_api,
)


def _make_mock_httpx_client(json_data, status_code=200):
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = json_data
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


class TestFetchMarketCapFromApi:
    @pytest.mark.asyncio
    @patch("app.services.market_cap.httpx.AsyncClient")
    async def test_returns_market_cap(self, mock_client_cls):
        mock_client = _make_mock_httpx_client(
            [{"symbol": "AAPL", "marketCap": 3759435415339.0}]
        )
        mock_client_cls.return_value = mock_client

        result = await _fetch_market_cap_from_api("AAPL")
        assert result == 3759435415339.0

    @pytest.mark.asyncio
    @patch("app.services.market_cap.httpx.AsyncClient")
    async def test_returns_none_on_empty(self, mock_client_cls):
        mock_client = _make_mock_httpx_client([])
        mock_client_cls.return_value = mock_client

        result = await _fetch_market_cap_from_api("INVALID")
        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.market_cap.httpx.AsyncClient")
    async def test_returns_none_on_error_status(self, mock_client_cls):
        mock_client = _make_mock_httpx_client([], status_code=500)
        mock_client_cls.return_value = mock_client

        result = await _fetch_market_cap_from_api("AAPL")
        assert result is None


class TestFetchMarketCap:
    @pytest.mark.asyncio
    @patch("app.services.market_cap.set_cached_market_cap")
    @patch("app.services.market_cap.get_cached_market_cap")
    async def test_returns_cached_value(self, mock_get_cache, mock_set_cache):
        mock_get_cache.return_value = 3.7e12

        result = await fetch_market_cap("AAPL")
        assert result == 3.7e12
        mock_set_cache.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.market_cap.httpx.AsyncClient")
    @patch("app.services.market_cap.set_cached_market_cap")
    @patch("app.services.market_cap.get_cached_market_cap")
    async def test_fetches_and_caches_on_miss(self, mock_get_cache, mock_set_cache, mock_client_cls):
        mock_get_cache.return_value = None
        mock_client = _make_mock_httpx_client(
            [{"symbol": "AAPL", "marketCap": 3.7e12}]
        )
        mock_client_cls.return_value = mock_client

        result = await fetch_market_cap("AAPL")
        assert result == 3.7e12
        mock_set_cache.assert_called_once_with("AAPL", 3.7e12)


class TestFetchMarketCapsBatch:
    @pytest.mark.asyncio
    @patch("app.services.market_cap.get_many_cached_market_caps")
    async def test_all_cached(self, mock_get_many):
        mock_get_many.return_value = {"AAPL": 3.7e12, "MSFT": 2.5e12}

        result = await fetch_market_caps_batch(["AAPL", "MSFT"])
        assert result["AAPL"] == 3.7e12
        assert result["MSFT"] == 2.5e12

    @pytest.mark.asyncio
    @patch("app.services.market_cap.set_many_cached_market_caps")
    @patch("app.services.market_cap._fetch_market_cap_from_api")
    @patch("app.services.market_cap.get_many_cached_market_caps")
    async def test_partial_cache_miss(self, mock_get_many, mock_api_fetch, mock_set_many):
        mock_get_many.return_value = {"AAPL": 3.7e12, "MSFT": None}
        mock_api_fetch.return_value = 2.5e12

        result = await fetch_market_caps_batch(["AAPL", "MSFT"])
        assert result["AAPL"] == 3.7e12
        assert result["MSFT"] == 2.5e12
        mock_api_fetch.assert_called_once_with("MSFT")
        mock_set_many.assert_called_once_with({"MSFT": 2.5e12})

    @pytest.mark.asyncio
    async def test_empty_tickers(self):
        result = await fetch_market_caps_batch([])
        assert result == {}

    @pytest.mark.asyncio
    @patch("app.services.market_cap.set_many_cached_market_caps")
    @patch("app.services.market_cap._fetch_market_cap_from_api")
    @patch("app.services.market_cap.get_many_cached_market_caps")
    async def test_deduplicates_tickers(self, mock_get_many, mock_api_fetch, mock_set_many):
        mock_get_many.return_value = {"AAPL": None}
        mock_api_fetch.return_value = 3.7e12

        result = await fetch_market_caps_batch(["AAPL", "AAPL", "AAPL"])
        assert mock_api_fetch.call_count == 1
