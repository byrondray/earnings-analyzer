from unittest.mock import patch, AsyncMock

import pytest


class TestAnalyzeEndpoint:
    @pytest.mark.asyncio
    async def test_post_analyze_returns_result(self, async_client, sample_analysis_result):
        result = {**sample_analysis_result, "ticker": "AAPL", "quarter": "Q4-2025"}
        with patch(
            "app.routers.analysis.run_analysis",
            new_callable=AsyncMock,
            return_value=result,
        ):
            response = await async_client.post(
                "/api/analysis/AAPL", params={"quarter": "Q4-2025"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "AAPL"
        assert data["eps_actual"] == 2.45
        assert data["sentiment"] == "bullish"

    @pytest.mark.asyncio
    async def test_post_analyze_returns_502_on_error(self, async_client):
        with patch(
            "app.routers.analysis.run_analysis",
            new_callable=AsyncMock,
            return_value={"error": "Claude did not return a tool use response"},
        ):
            response = await async_client.post(
                "/api/analysis/AAPL", params={"quarter": "Q4-2025"}
            )

        assert response.status_code == 502

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
