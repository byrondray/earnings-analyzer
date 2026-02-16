from datetime import date
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from app.services.earnings_calendar import (
    week_bounds,
    _map_report_time,
    fetch_all_earnings_from_alpha_vantage,
    _parse_nasdaq_eps_forecast,
    _normalize_fiscal_quarter,
    _fetch_historical_earnings_nasdaq,
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


class TestFetchAllEarningsFromAlphaVantage:
    @pytest.mark.asyncio
    async def test_fetch_returns_all_parsed_csv(self):
        mock_client = _make_mock_httpx_client(SAMPLE_AV_CSV)

        with patch("app.services.earnings_calendar.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_all_earnings_from_alpha_vantage()

        assert len(result) == 4
        assert result[0]["symbol"] == "AAPL"
        assert result[1]["symbol"] == "MSFT"
        assert result[2]["symbol"] == "GOOGL"
        assert result[3]["symbol"] == "TSLA"

    @pytest.mark.asyncio
    async def test_fetch_returns_empty_on_error(self):
        mock_client = _make_mock_httpx_client("", status_code=500)

        with patch("app.services.earnings_calendar.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_all_earnings_from_alpha_vantage()

        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_maps_eps_estimate(self):
        mock_client = _make_mock_httpx_client(SAMPLE_AV_CSV)

        with patch("app.services.earnings_calendar.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_all_earnings_from_alpha_vantage()

        assert result[0]["epsEstimated"] == 2.35


class TestNormalizeFiscalQuarter:
    def test_nasdaq_format(self):
        assert _normalize_fiscal_quarter("Dec/2025") == "2025-12-31"

    def test_nasdaq_format_march(self):
        assert _normalize_fiscal_quarter("Mar/2025") == "2025-03-31"

    def test_nasdaq_format_feb(self):
        assert _normalize_fiscal_quarter("Feb/2024") == "2024-02-29"

    def test_iso_passthrough(self):
        assert _normalize_fiscal_quarter("2025-12-31") == "2025-12-31"

    def test_none(self):
        assert _normalize_fiscal_quarter(None) is None


class TestParseNasdaqEpsForecast:
    def test_normal_value(self):
        assert _parse_nasdaq_eps_forecast("$2.35") == 2.35

    def test_negative_parenthesized(self):
        assert _parse_nasdaq_eps_forecast("($0.13)") == -0.13

    def test_empty_string(self):
        assert _parse_nasdaq_eps_forecast("") is None

    def test_none(self):
        assert _parse_nasdaq_eps_forecast(None) is None

    def test_no_dollar_sign(self):
        assert _parse_nasdaq_eps_forecast("1.50") == 1.50


class TestFetchHistoricalEarningsNasdaq:
    @pytest.mark.asyncio
    async def test_fetches_weekdays_only(self):
        nasdaq_response = {
            "data": {
                "rows": [
                    {
                        "symbol": "AAPL",
                        "name": "Apple Inc.",
                        "epsForecast": "$2.35",
                        "time": "time-not-supplied",
                        "fiscalQuarterEnding": "Dec/2025",
                    }
                ]
            }
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value=nasdaq_response)

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.earnings_calendar.httpx.AsyncClient", return_value=mock_client):
            result = await _fetch_historical_earnings_nasdaq(
                date(2025, 7, 7), date(2025, 7, 11)
            )

        assert mock_client.get.call_count == 5
        assert len(result) == 5
        assert result[0]["symbol"] == "AAPL"
        assert result[0]["date"] == "2025-07-07"
        assert result[0]["epsEstimated"] == 2.35

    @pytest.mark.asyncio
    async def test_skips_weekends(self):
        nasdaq_response = {"data": {"rows": [{"symbol": "TEST", "name": "Test"}]}}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value=nasdaq_response)

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.earnings_calendar.httpx.AsyncClient", return_value=mock_client):
            result = await _fetch_historical_earnings_nasdaq(
                date(2025, 7, 5), date(2025, 7, 6)
            )

        assert mock_client.get.call_count == 0
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_handles_api_error_gracefully(self):
        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.earnings_calendar.httpx.AsyncClient", return_value=mock_client):
            result = await _fetch_historical_earnings_nasdaq(
                date(2025, 7, 7), date(2025, 7, 11)
            )

        assert result == []
