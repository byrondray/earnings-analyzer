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
def sample_nasdaq_response():
    return {
        "data": {
            "rows": [
                {
                    "symbol": "AAPL",
                    "name": "Apple Inc.",
                    "eps": "$2.45",
                    "epsForecast": "$2.35",
                    "surprise": "$0.10",
                    "time": "time-not-supplied",
                    "marketCap": "$3,450,000,000,000",
                    "fiscalQuarterEnding": "Dec/2025",
                    "noOfEsts": "30",
                },
                {
                    "symbol": "MSFT",
                    "name": "Microsoft Corporation",
                    "eps": "$3.25",
                    "epsForecast": "$3.12",
                    "surprise": "$0.13",
                    "time": "time-not-supplied",
                    "marketCap": "$2,800,000,000,000",
                    "fiscalQuarterEnding": "Dec/2025",
                    "noOfEsts": "28",
                },
            ]
        }
    }


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
