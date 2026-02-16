from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.services.cache import (
    get_cached_market_cap,
    set_cached_market_cap,
    get_many_cached_market_caps,
    set_many_cached_market_caps,
    get_cached_calendar,
    set_cached_calendar,
    get_cached_analysis_redis,
    set_cached_analysis_redis,
    _market_cap_key,
    _calendar_key,
    _analysis_key,
    MARKET_CAP_TTL,
    EARNINGS_CALENDAR_TTL,
    ANALYSIS_TTL,
)


class TestCacheKeys:
    def test_market_cap_key(self):
        assert _market_cap_key("aapl") == "earnings:mcap:AAPL"
        assert _market_cap_key("MSFT") == "earnings:mcap:MSFT"

    def test_calendar_key(self):
        assert _calendar_key("2026-02-16") == "earnings:calendar:2026-02-16"

    def test_analysis_key(self):
        assert _analysis_key("aapl", "Q4-2025") == "earnings:analysis:AAPL:Q4-2025"
        assert _analysis_key("MSFT", "Q1-2026") == "earnings:analysis:MSFT:Q1-2026"


class TestMarketCapCache:
    @pytest.mark.asyncio
    @patch("app.services.cache.get_redis")
    async def test_get_cached_market_cap_returns_float(self, mock_get_redis):
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="3759435415339.0")
        mock_get_redis.return_value = mock_redis

        result = await get_cached_market_cap("AAPL")
        assert result == 3759435415339.0
        mock_redis.get.assert_called_once_with("earnings:mcap:AAPL")

    @pytest.mark.asyncio
    @patch("app.services.cache.get_redis")
    async def test_get_cached_market_cap_returns_none_on_miss(self, mock_get_redis):
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_get_redis.return_value = mock_redis

        result = await get_cached_market_cap("AAPL")
        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.cache.get_redis")
    async def test_get_cached_market_cap_no_redis(self, mock_get_redis):
        mock_get_redis.return_value = None
        result = await get_cached_market_cap("AAPL")
        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.cache.get_redis")
    async def test_set_cached_market_cap(self, mock_get_redis):
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis

        await set_cached_market_cap("AAPL", 3759435415339.0)
        mock_redis.setex.assert_called_once_with(
            "earnings:mcap:AAPL", MARKET_CAP_TTL, "3759435415339.0"
        )

    @pytest.mark.asyncio
    @patch("app.services.cache.get_redis")
    async def test_get_many_cached_market_caps(self, mock_get_redis):
        mock_redis = AsyncMock()
        mock_redis.mget = AsyncMock(return_value=["3759435415339.0", None, "2000000000000.0"])
        mock_get_redis.return_value = mock_redis

        result = await get_many_cached_market_caps(["AAPL", "MSFT", "GOOGL"])
        assert result == {
            "AAPL": 3759435415339.0,
            "MSFT": None,
            "GOOGL": 2000000000000.0,
        }

    @pytest.mark.asyncio
    @patch("app.services.cache.get_redis")
    async def test_set_many_cached_market_caps(self, mock_get_redis):
        mock_redis = AsyncMock()
        mock_pipe = AsyncMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)
        mock_get_redis.return_value = mock_redis

        await set_many_cached_market_caps({"AAPL": 3.7e12, "MSFT": 2.5e12})
        assert mock_pipe.setex.call_count == 2
        mock_pipe.execute.assert_called_once()


class TestCalendarCache:
    @pytest.mark.asyncio
    @patch("app.services.cache.get_redis")
    async def test_get_cached_calendar(self, mock_get_redis):
        import json
        events = [{"symbol": "AAPL", "date": "2026-02-16"}]
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(events))
        mock_get_redis.return_value = mock_redis

        result = await get_cached_calendar("2026-02-16")
        assert result == events

    @pytest.mark.asyncio
    @patch("app.services.cache.get_redis")
    async def test_set_cached_calendar(self, mock_get_redis):
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis

        events = [{"symbol": "AAPL"}]
        await set_cached_calendar("2026-02-16", events)
        mock_redis.setex.assert_called_once()


class TestGracefulDegradation:
    @pytest.mark.asyncio
    @patch("app.services.cache.get_redis")
    async def test_get_market_cap_handles_exception(self, mock_get_redis):
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=Exception("Connection refused"))
        mock_get_redis.return_value = mock_redis

        result = await get_cached_market_cap("AAPL")
        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.cache.get_redis")
    async def test_set_market_cap_handles_exception(self, mock_get_redis):
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock(side_effect=Exception("Connection refused"))
        mock_get_redis.return_value = mock_redis

        await set_cached_market_cap("AAPL", 1.0)


class TestAnalysisCache:
    @pytest.mark.asyncio
    @patch("app.services.cache.get_redis")
    async def test_get_cached_analysis_returns_dict(self, mock_get_redis):
        import json
        analysis = {"ticker": "AAPL", "sentiment": "bullish", "eps_actual": 2.45}
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(analysis))
        mock_get_redis.return_value = mock_redis

        result = await get_cached_analysis_redis("AAPL", "Q4-2025")
        assert result == analysis
        mock_redis.get.assert_called_once_with("earnings:analysis:AAPL:Q4-2025")

    @pytest.mark.asyncio
    @patch("app.services.cache.get_redis")
    async def test_get_cached_analysis_returns_none_on_miss(self, mock_get_redis):
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_get_redis.return_value = mock_redis

        result = await get_cached_analysis_redis("AAPL", "Q4-2025")
        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.cache.get_redis")
    async def test_get_cached_analysis_no_redis(self, mock_get_redis):
        mock_get_redis.return_value = None
        result = await get_cached_analysis_redis("AAPL", "Q4-2025")
        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.cache.get_redis")
    async def test_set_cached_analysis(self, mock_get_redis):
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis

        analysis = {"ticker": "AAPL", "sentiment": "bullish"}
        await set_cached_analysis_redis("AAPL", "Q4-2025", analysis)
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == "earnings:analysis:AAPL:Q4-2025"
        assert call_args[0][1] == ANALYSIS_TTL

    @pytest.mark.asyncio
    @patch("app.services.cache.get_redis")
    async def test_get_cached_analysis_handles_exception(self, mock_get_redis):
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=Exception("Connection refused"))
        mock_get_redis.return_value = mock_redis

        result = await get_cached_analysis_redis("AAPL", "Q4-2025")
        assert result is None
