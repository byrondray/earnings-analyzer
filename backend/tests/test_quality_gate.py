from datetime import date, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.services.analysis import _apply_quality_gate

_EASTERN = ZoneInfo("America/New_York")


def _event_context(report_date: str, report_time: str) -> dict:
    return {
        "company_name": "Example Corp",
        "report_date": report_date,
        "report_time": report_time,
        "eps_estimate": 1.0,
        "revenue_estimate": 100.0,
        "fiscal_quarter": None,
    }


class TestFutureReportDateGate:
    def test_same_day_post_market_before_release_cutoff_stays_unreported(self):
        event_context = _event_context("2026-08-12", "post_market")
        analysis = {"has_reported": True, "citations": []}

        with patch(
            "app.services.analysis.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 8, 12, 15, 0, tzinfo=_EASTERN)
            result = _apply_quality_gate(analysis, event_context)

        assert result["has_reported"] is False
        assert "future_report_date" in result["quality_flags"]

    def test_same_day_post_market_after_release_cutoff_is_not_forced_unreported(self):
        event_context = _event_context("2026-08-12", "post_market")
        analysis = {"has_reported": True, "citations": []}

        with patch(
            "app.services.analysis.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 8, 12, 18, 0, tzinfo=_EASTERN)
            result = _apply_quality_gate(analysis, event_context)

        assert result["has_reported"] is True
        assert "future_report_date" not in result["quality_flags"]

    def test_strictly_future_date_is_still_forced_unreported(self):
        event_context = _event_context("2026-08-20", "post_market")
        analysis = {"has_reported": True, "citations": []}

        with patch(
            "app.services.analysis.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 8, 12, 18, 0, tzinfo=_EASTERN)
            result = _apply_quality_gate(analysis, event_context)

        assert result["has_reported"] is False
        assert "future_report_date" in result["quality_flags"]

    def test_same_day_pre_market_is_not_forced_unreported(self):
        event_context = _event_context("2026-08-12", "pre_market")
        analysis = {"has_reported": True, "citations": []}

        with patch(
            "app.services.analysis.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 8, 12, 9, 0, tzinfo=_EASTERN)
            result = _apply_quality_gate(analysis, event_context)

        assert result["has_reported"] is True
        assert "future_report_date" not in result["quality_flags"]
