import asyncio
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_fmp_response():
    return [
        {
            "date": "2026-02-16",
            "symbol": "AAPL",
            "companyName": "Apple Inc.",
            "time": "amc",
            "epsEstimated": 2.35,
            "revenueEstimated": 94900000000,
            "fiscalDateEnding": "2025-12-31",
        },
        {
            "date": "2026-02-17",
            "symbol": "MSFT",
            "companyName": "Microsoft Corporation",
            "time": "bmo",
            "epsEstimated": 3.12,
            "revenueEstimated": 65800000000,
            "fiscalDateEnding": "2025-12-31",
        },
        {
            "date": "2026-02-18",
            "symbol": "GOOGL",
            "companyName": "Alphabet Inc.",
            "time": "amc",
            "epsEstimated": 1.87,
            "revenueEstimated": 86200000000,
            "fiscalDateEnding": "2025-12-31",
        },
    ]


@pytest.fixture
def sample_brave_response():
    return {
        "web": {
            "results": [
                {
                    "title": "Apple Q4 2025 Earnings: Revenue Beats Estimates",
                    "url": "https://example.com/aapl-earnings",
                    "description": "Apple reported Q4 2025 EPS of $2.45 vs $2.35 estimated. Revenue came in at $95.4B vs $94.9B expected.",
                },
                {
                    "title": "AAPL Earnings Call Highlights",
                    "url": "https://example.com/aapl-call",
                    "description": "Tim Cook outlined strong iPhone demand and raised guidance for Q1 2026.",
                },
                {
                    "title": "Apple Stock Rises After Earnings Beat",
                    "url": "https://example.com/aapl-stock",
                    "description": "AAPL shares rose 3.2% in after-hours trading following the earnings beat.",
                },
            ]
        }
    }


@pytest.fixture
def sample_analysis_result():
    return {
        "eps_estimate": 2.35,
        "eps_actual": 2.45,
        "eps_surprise_pct": 4.26,
        "revenue_estimate": 94900000000,
        "revenue_actual": 95400000000,
        "revenue_surprise_pct": 0.53,
        "guidance_summary": "Apple raised guidance for Q1 2026, citing strong iPhone demand and growing services revenue.",
        "sentiment": "bullish",
        "sentiment_score": 0.85,
        "price_reaction_pct": 3.2,
    }


@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
