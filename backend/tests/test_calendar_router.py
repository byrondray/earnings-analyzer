from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock

import pytest


class TestCalendarWeekEndpoint:
    @pytest.mark.asyncio
    async def test_get_week_returns_200(self, async_client):
        mock_events = []
        with patch(
            "app.routers.calendar.get_week_earnings",
            new_callable=AsyncMock,
            return_value=mock_events,
        ):
            response = await async_client.get(
                "/api/calendar/week", params={"date": "2026-02-16"}
            )

        assert response.status_code == 200
        data = response.json()
        assert "week_start" in data
        assert "week_end" in data
        assert "events" in data
        assert isinstance(data["events"], list)

    @pytest.mark.asyncio
    async def test_get_week_correct_bounds(self, async_client):
        with patch(
            "app.routers.calendar.get_week_earnings",
            new_callable=AsyncMock,
            return_value=[],
        ):
            response = await async_client.get(
                "/api/calendar/week", params={"date": "2026-02-18"}
            )

        data = response.json()
        assert data["week_start"] == "2026-02-16"
        assert data["week_end"] == "2026-02-20"

    @pytest.mark.asyncio
    async def test_get_week_defaults_to_today(self, async_client):
        with patch(
            "app.routers.calendar.get_week_earnings",
            new_callable=AsyncMock,
            return_value=[],
        ):
            response = await async_client.get("/api/calendar/week")

        assert response.status_code == 200


class TestCalendarNextPrevEndpoints:
    @pytest.mark.asyncio
    async def test_next_week_returns_200(self, async_client):
        with patch(
            "app.routers.calendar.get_week_earnings",
            new_callable=AsyncMock,
            return_value=[],
        ):
            response = await async_client.get(
                "/api/calendar/week/next", params={"date": "2026-02-16"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["week_start"] == "2026-02-23"
        assert data["week_end"] == "2026-02-27"

    @pytest.mark.asyncio
    async def test_prev_week_returns_200(self, async_client):
        with patch(
            "app.routers.calendar.get_week_earnings",
            new_callable=AsyncMock,
            return_value=[],
        ):
            response = await async_client.get(
                "/api/calendar/week/prev", params={"date": "2026-02-16"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["week_start"] == "2026-02-09"
        assert data["week_end"] == "2026-02-13"


def _make_event(ticker, report_date, market_cap=None):
    return SimpleNamespace(
        id=1,
        ticker=ticker,
        company_name=f"{ticker} Inc.",
        report_date=report_date,
        report_time="unknown",
        fiscal_quarter="2025-12-31",
        eps_estimate=1.50,
        revenue_estimate=None,
        market_cap=market_cap,
    )


class TestHighlightsEndpoint:
    @pytest.mark.asyncio
    async def test_highlights_returns_200(self, async_client):
        with patch(
            "app.routers.calendar.get_week_earnings",
            new_callable=AsyncMock,
            return_value=[],
        ):
            response = await async_client.get("/api/calendar/highlights")

        assert response.status_code == 200
        data = response.json()
        assert "last_week" in data
        assert "this_week" in data
        assert "events" in data["last_week"]
        assert "events" in data["this_week"]

    @pytest.mark.asyncio
    async def test_highlights_sorted_by_market_cap(self, async_client):
        today = date.today()
        monday = today - timedelta(days=today.weekday())

        mock_events = [
            _make_event("SMALL", monday, market_cap=1_000_000),
            _make_event("BIG", monday, market_cap=1_000_000_000_000),
            _make_event("MID", monday, market_cap=50_000_000_000),
        ]

        with patch(
            "app.routers.calendar.get_week_earnings",
            new_callable=AsyncMock,
            return_value=mock_events,
        ):
            response = await async_client.get("/api/calendar/highlights")

        data = response.json()
        this_tickers = [e["ticker"] for e in data["this_week"]["events"]]
        assert this_tickers == ["BIG", "MID", "SMALL"]

    @pytest.mark.asyncio
    async def test_highlights_limited_to_10(self, async_client):
        today = date.today()
        monday = today - timedelta(days=today.weekday())

        mock_events = [
            _make_event(f"T{i}", monday, market_cap=(15 - i) * 1e9)
            for i in range(15)
        ]

        with patch(
            "app.routers.calendar.get_week_earnings",
            new_callable=AsyncMock,
            return_value=mock_events,
        ):
            response = await async_client.get("/api/calendar/highlights")

        data = response.json()
        assert len(data["this_week"]["events"]) == 10
