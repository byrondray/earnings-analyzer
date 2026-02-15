from datetime import date, datetime

from app.db.models import (
    EarningsEvent,
    EarningsAnalysis,
    ReportTime,
    Sentiment,
    Base,
)


class TestEarningsEventModel:
    def test_create_earnings_event(self):
        event = EarningsEvent(
            ticker="AAPL",
            company_name="Apple Inc.",
            report_date=date(2026, 2, 16),
            report_time=ReportTime.POST_MARKET,
            fiscal_quarter="2025-12-31",
            eps_estimate=2.35,
            revenue_estimate=94900000000,
        )
        assert event.ticker == "AAPL"
        assert event.company_name == "Apple Inc."
        assert event.report_date == date(2026, 2, 16)
        assert event.report_time == ReportTime.POST_MARKET
        assert event.eps_estimate == 2.35

    def test_report_time_enum_values(self):
        assert ReportTime.PRE_MARKET.value == "pre_market"
        assert ReportTime.POST_MARKET.value == "post_market"
        assert ReportTime.UNKNOWN.value == "unknown"

    def test_sentiment_enum_values(self):
        assert Sentiment.BULLISH.value == "bullish"
        assert Sentiment.BEARISH.value == "bearish"
        assert Sentiment.NEUTRAL.value == "neutral"


class TestEarningsAnalysisModel:
    def test_create_earnings_analysis(self, sample_analysis_result):
        analysis = EarningsAnalysis(
            earnings_event_id=1,
            eps_estimate=sample_analysis_result["eps_estimate"],
            eps_actual=sample_analysis_result["eps_actual"],
            eps_surprise_pct=sample_analysis_result["eps_surprise_pct"],
            revenue_estimate=sample_analysis_result["revenue_estimate"],
            revenue_actual=sample_analysis_result["revenue_actual"],
            revenue_surprise_pct=sample_analysis_result["revenue_surprise_pct"],
            guidance_summary=sample_analysis_result["guidance_summary"],
            sentiment=Sentiment.BULLISH,
            sentiment_score=0.85,
            price_reaction_pct=3.2,
            raw_analysis=sample_analysis_result,
        )
        assert analysis.earnings_event_id == 1
        assert analysis.eps_actual == 2.45
        assert analysis.sentiment == Sentiment.BULLISH
        assert analysis.raw_analysis is not None

    def test_analysis_nullable_fields(self):
        analysis = EarningsAnalysis(
            earnings_event_id=1,
        )
        assert analysis.eps_estimate is None
        assert analysis.eps_actual is None
        assert analysis.guidance_summary is None
        assert analysis.sentiment is None


class TestTableMetadata:
    def test_earnings_events_table_exists(self):
        assert "earnings_events" in Base.metadata.tables

    def test_earnings_analyses_table_exists(self):
        assert "earnings_analyses" in Base.metadata.tables

    def test_unique_constraint_on_ticker_date(self):
        table = Base.metadata.tables["earnings_events"]
        constraint_names = [c.name for c in table.constraints if c.name]
        assert "uq_ticker_report_date" in constraint_names
