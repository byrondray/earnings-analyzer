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
