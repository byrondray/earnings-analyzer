from datetime import date
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from app.services.earnings_calendar import (
    week_bounds,
    _map_report_time,
    fetch_earnings_from_alpha_vantage,
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
        assert _map_report_time("pre-market") == ReportTime.PRE_MARKET

    def test_after_market_close(self):
        assert _map_report_time("amc") == ReportTime.POST_MARKET
        assert _map_report_time("after market close") == ReportTime.POST_MARKET
        assert _map_report_time("post-market") == ReportTime.POST_MARKET

    def test_unknown(self):
        assert _map_report_time(None) == ReportTime.UNKNOWN
        assert _map_report_time("") == ReportTime.UNKNOWN
        assert _map_report_time("during") == ReportTime.UNKNOWN


SAMPLE_AV_CSV = """symbol,name,reportDate,fiscalDateEnding,estimate,currency,timeOfTheDay
AAPL,Apple Inc.,2026-02-16,2025-12-31,2.35,USD,post-market
MSFT,Microsoft Corporation,2026-02-17,2025-12-31,3.12,USD,pre-market
GOOGL,Alphabet Inc.,2026-02-18,2025-12-31,1.87,USD,post-market
TSLA,Tesla Inc.,2026-02-25,2025-12-31,0.95,USD,post-market
"""


def _make_mock_httpx_client(response_text, status_code=200):
    mock_response = MagicMock()
    mock_response.text = response_text
    mock_response.status_code = status_code

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestFetchEarningsFromAlphaVantage:
    @pytest.mark.asyncio
    async def test_fetch_returns_parsed_csv_filtered_by_date(self):
        mock_client = _make_mock_httpx_client(SAMPLE_AV_CSV)

        with patch("app.services.earnings_calendar.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_earnings_from_alpha_vantage(date(2026, 2, 16), date(2026, 2, 20))

        assert len(result) == 3
        assert result[0]["symbol"] == "AAPL"
        assert result[1]["symbol"] == "MSFT"
        assert result[2]["symbol"] == "GOOGL"

    @pytest.mark.asyncio
    async def test_fetch_excludes_out_of_range_dates(self):
        mock_client = _make_mock_httpx_client(SAMPLE_AV_CSV)

        with patch("app.services.earnings_calendar.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_earnings_from_alpha_vantage(date(2026, 2, 16), date(2026, 2, 20))

        symbols = [r["symbol"] for r in result]
        assert "TSLA" not in symbols

    @pytest.mark.asyncio
    async def test_fetch_returns_empty_on_error(self):
        mock_client = _make_mock_httpx_client("", status_code=500)

        with patch("app.services.earnings_calendar.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_earnings_from_alpha_vantage(date(2026, 2, 16), date(2026, 2, 20))

        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_maps_eps_estimate(self):
        mock_client = _make_mock_httpx_client(SAMPLE_AV_CSV)

        with patch("app.services.earnings_calendar.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_earnings_from_alpha_vantage(date(2026, 2, 16), date(2026, 2, 20))

        assert result[0]["epsEstimated"] == 2.35
