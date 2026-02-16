import json
from unittest.mock import patch, AsyncMock

import pytest


async def _mock_streaming_result(result):
    yield ("status", {"step": "cache", "message": "Checking cache..."})
    yield ("result", result)


async def _mock_streaming_error():
    yield ("error", {"error": "Claude did not return a tool use response"})


class TestAnalyzeEndpoint:
    @pytest.mark.asyncio
    async def test_post_analyze_returns_sse_result(self, async_client, sample_analysis_result):
        result = {**sample_analysis_result, "ticker": "AAPL", "quarter": "Q4-2025"}

        with patch(
            "app.routers.analysis.run_analysis_streaming",
            return_value=_mock_streaming_result(result),
        ):
            response = await async_client.post(
                "/api/analysis/AAPL", params={"quarter": "Q4-2025"}
            )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        lines = response.text.strip().split("\n")
        events = []
        event_type = None
        for line in lines:
            if line.startswith("event: "):
                event_type = line[7:].strip()
            elif line.startswith("data: ") and event_type:
                events.append((event_type, json.loads(line[6:])))
                event_type = None

        result_events = [e for e in events if e[0] == "result"]
        assert len(result_events) == 1
        assert result_events[0][1]["ticker"] == "AAPL"
        assert result_events[0][1]["eps_actual"] == 2.45

    @pytest.mark.asyncio
    async def test_post_analyze_streams_error(self, async_client):
        with patch(
            "app.routers.analysis.run_analysis_streaming",
            return_value=_mock_streaming_error(),
        ):
            response = await async_client.post(
                "/api/analysis/AAPL", params={"quarter": "Q4-2025"}
            )

        assert response.status_code == 200
        assert "error" in response.text

    @pytest.mark.asyncio
    async def test_post_analyze_requires_quarter_param(self, async_client):
        response = await async_client.post("/api/analysis/AAPL")
        assert response.status_code == 422


class TestGetAnalysisEndpoint:
    @pytest.mark.asyncio
    async def test_get_cached_returns_result(self, async_client, sample_analysis_result):
        cached = {
            **sample_analysis_result,
            "id": 1,
            "earnings_event_id": 1,
            "ticker": "AAPL",
            "raw_analysis": sample_analysis_result,
            "analyzed_at": "2026-02-16T10:00:00",
        }
        with patch(
            "app.routers.analysis.get_cached_analysis",
            new_callable=AsyncMock,
            return_value=cached,
        ):
            response = await async_client.get("/api/analysis/AAPL")

        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "AAPL"

    @pytest.mark.asyncio
    async def test_get_cached_returns_404_when_missing(self, async_client):
        with patch(
            "app.routers.analysis.get_cached_analysis",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = await async_client.get("/api/analysis/XYZ")

        assert response.status_code == 404
        assert "XYZ" in response.json()["detail"]
