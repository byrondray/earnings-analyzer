from datetime import date
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from app.services.earnings_calendar import (
    week_bounds,
    _map_report_time,
    fetch_earnings_from_fmp,
)
from app.db.models import ReportTime


class TestWeekBounds:
    def test_monday_input(self):
        monday, friday = week_bounds(date(2026, 2, 16))
        assert monday == date(2026, 2, 16)
        assert friday == date(2026, 2, 20)

    def test_wednesday_input(self):
        monday, friday = week_bounds(date(2026, 2, 18))
        assert monday == date(2026, 2, 16)
        assert friday == date(2026, 2, 20)

    def test_friday_input(self):
        monday, friday = week_bounds(date(2026, 2, 20))
        assert monday == date(2026, 2, 16)
        assert friday == date(2026, 2, 20)

    def test_sunday_maps_to_correct_week(self):
        monday, friday = week_bounds(date(2026, 2, 15))
        assert monday == date(2026, 2, 9)
        assert friday == date(2026, 2, 13)

    def test_saturday_maps_to_correct_week(self):
        monday, friday = week_bounds(date(2026, 2, 14))
        assert monday == date(2026, 2, 9)
        assert friday == date(2026, 2, 13)


class TestMapReportTime:
    def test_before_market_open(self):
        assert _map_report_time("bmo") == ReportTime.PRE_MARKET
        assert _map_report_time("before market open") == ReportTime.PRE_MARKET

    def test_after_market_close(self):
        assert _map_report_time("amc") == ReportTime.POST_MARKET
        assert _map_report_time("after market close") == ReportTime.POST_MARKET

    def test_unknown(self):
        assert _map_report_time(None) == ReportTime.UNKNOWN
        assert _map_report_time("") == ReportTime.UNKNOWN
        assert _map_report_time("during") == ReportTime.UNKNOWN


def _make_mock_httpx_client(response_data):
    """httpx Response.json() is synchronous, so use MagicMock for the response."""
    mock_response = MagicMock()
    mock_response.json.return_value = response_data
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestFetchEarningsFromFmp:
    @pytest.mark.asyncio
    async def test_fetch_returns_parsed_json(self, sample_fmp_response):
        mock_client = _make_mock_httpx_client(sample_fmp_response)

        with patch("app.services.earnings_calendar.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_earnings_from_fmp(date(2026, 2, 16), date(2026, 2, 20))

        assert len(result) == 3
        assert result[0]["symbol"] == "AAPL"
        assert result[1]["symbol"] == "MSFT"

    @pytest.mark.asyncio
    async def test_fetch_passes_correct_params(self):
        mock_client = _make_mock_httpx_client([])

        with patch("app.services.earnings_calendar.httpx.AsyncClient", return_value=mock_client):
            await fetch_earnings_from_fmp(date(2026, 2, 16), date(2026, 2, 20))

        call_args = mock_client.get.call_args
        params = call_args.kwargs.get("params") or call_args[1].get("params")
        assert params["from"] == "2026-02-16"
        assert params["to"] == "2026-02-20"
