from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.models import EarningsAnalysis, Sentiment, _utcnow_naive
from app.services.analysis import get_cached_analysis
from app.services.cache import ANALYSIS_UNREPORTED_TTL


def _make_analysis(has_reported, analyzed_at, sentiment=Sentiment.BULLISH):
    analysis = MagicMock(spec=EarningsAnalysis)
    analysis.id = 1
    analysis.earnings_event_id = 10
    analysis.eps_estimate = 2.35
    analysis.eps_actual = 2.45 if has_reported else None
    analysis.eps_surprise_pct = 4.26 if has_reported else None
    analysis.revenue_estimate = 94_900_000_000
    analysis.revenue_actual = 95_400_000_000 if has_reported else None
    analysis.revenue_surprise_pct = 0.53 if has_reported else None
    analysis.guidance_summary = "Strong guidance" if has_reported else None
    analysis.sentiment = sentiment
    analysis.sentiment_score = 0.85
    analysis.price_reaction_pct = 3.2 if has_reported else None
    analysis.raw_analysis = {"has_reported": has_reported}
    analysis.analyzed_at = analyzed_at
    return analysis


def _mock_db(analysis_obj):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = analysis_obj
    db = AsyncMock()
    db.execute.return_value = mock_result
    return db


class TestGetCachedAnalysisStaleness:
    @pytest.mark.asyncio
    async def test_reported_analysis_is_never_stale(self):
        old_time = _utcnow_naive() - timedelta(days=10)
        analysis = _make_analysis(has_reported=True, analyzed_at=old_time)
        db = _mock_db(analysis)

        result = await get_cached_analysis(db, "AAPL")

        assert result["has_reported"] is True
        assert result["stale"] is False

    @pytest.mark.asyncio
    async def test_unreported_analysis_fresh_within_ttl(self):
        recent_time = _utcnow_naive() - timedelta(hours=1)
        analysis = _make_analysis(has_reported=False, analyzed_at=recent_time)
        db = _mock_db(analysis)

        result = await get_cached_analysis(db, "AAPL")

        assert result["has_reported"] is False
        assert result["stale"] is False

    @pytest.mark.asyncio
    async def test_unreported_analysis_stale_after_ttl(self):
        old_time = _utcnow_naive() - timedelta(seconds=ANALYSIS_UNREPORTED_TTL + 60)
        analysis = _make_analysis(has_reported=False, analyzed_at=old_time)
        db = _mock_db(analysis)

        result = await get_cached_analysis(db, "AAPL")

        assert result["has_reported"] is False
        assert result["stale"] is True

    @pytest.mark.asyncio
    async def test_returns_none_when_no_analysis(self):
        db = _mock_db(None)

        result = await get_cached_analysis(db, "AAPL")

        assert result is None

    @pytest.mark.asyncio
    async def test_unreported_at_exact_ttl_boundary_is_stale(self):
        boundary_time = _utcnow_naive() - timedelta(seconds=ANALYSIS_UNREPORTED_TTL)
        analysis = _make_analysis(has_reported=False, analyzed_at=boundary_time)
        db = _mock_db(analysis)

        result = await get_cached_analysis(db, "AAPL")

        assert result["stale"] is True
