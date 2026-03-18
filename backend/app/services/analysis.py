from collections.abc import AsyncGenerator
from datetime import date, datetime, timedelta
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EarningsAnalysis, EarningsEvent
from app.mcp_server.tools.web_search import search_earnings_report
from app.mcp_server.tools.analyze import analyze_earnings

logger = logging.getLogger(__name__)

_PRIMARY_SOURCE_HINTS = [
    "businesswire.com",
    "prnewswire.com",
    "globenewswire.com",
    "sec.gov",
    "investor",
    "ir.",
    "investors.",
]


def _append_quality_flag(analysis: dict, flag: str):
    flags = analysis.get("quality_flags")
    if not isinstance(flags, list):
        flags = []
    if flag not in flags:
        flags.append(flag)
    analysis["quality_flags"] = flags


def _coerce_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp_confidence(value: object, fallback: float = 0.5) -> float:
    parsed = _coerce_float(value)
    if parsed is None:
        return fallback
    return max(0.0, min(1.0, parsed))


def _parse_report_date(event_context: dict | None) -> date | None:
    if not event_context:
        return None
    report_date = event_context.get("report_date")
    if not isinstance(report_date, str):
        return None
    try:
        return date.fromisoformat(report_date[:10])
    except ValueError:
        return None


def _recompute_surprise(actual: object, estimate: object) -> float | None:
    actual_num = _coerce_float(actual)
    estimate_num = _coerce_float(estimate)
    if actual_num is None or estimate_num is None or estimate_num == 0:
        return None
    return round(((actual_num - estimate_num) / abs(estimate_num)) * 100, 2)


def _normalize_citations(analysis: dict) -> list[dict]:
    citations = analysis.get("citations")
    if not isinstance(citations, list):
        citations = []

    normalized = []
    for citation in citations:
        if not isinstance(citation, dict):
            continue
        field_refs = citation.get("field_refs")
        if not isinstance(field_refs, list):
            field_refs = []

        normalized.append(
            {
                "url": str(citation.get("url", "")).strip(),
                "title": str(citation.get("title", "")).strip(),
                "excerpt": str(citation.get("excerpt", "")).strip(),
                "field_refs": [str(ref).strip() for ref in field_refs if str(ref).strip()],
            }
        )

    analysis["citations"] = normalized
    return normalized


def _has_primary_source(citations: list[dict]) -> bool:
    for citation in citations:
        url = str(citation.get("url", "")).lower()
        if any(hint in url for hint in _PRIMARY_SOURCE_HINTS):
            return True
    return False


def _has_field_citation(citations: list[dict], field_name: str) -> bool:
    for citation in citations:
        refs = citation.get("field_refs")
        if isinstance(refs, list) and field_name in refs:
            return True
    return False


def _apply_quality_gate(analysis: dict, event_context: dict | None) -> dict:
    analysis.setdefault("has_reported", True)
    analysis.setdefault("quality_flags", [])

    citations = _normalize_citations(analysis)
    if not citations:
        _append_quality_flag(analysis, "snippet_only_extraction")

    source_count = analysis.get("source_count")
    try:
        source_count = int(source_count)
    except (TypeError, ValueError):
        source_count = len({c.get("url") for c in citations if c.get("url")})
        if source_count == 0:
            source_count = len(citations)

    analysis["source_count"] = max(0, source_count)

    confidence = _clamp_confidence(analysis.get("confidence_score"), 0.5)

    if analysis["source_count"] < 2:
        _append_quality_flag(analysis, "low_source_count")
        confidence = min(confidence, 0.55)

    if not _has_primary_source(citations):
        _append_quality_flag(analysis, "missing_primary_source")

    report_date = _parse_report_date(event_context)
    if report_date and report_date >= date.today() and analysis.get("has_reported") is True:
        analysis["has_reported"] = False
        _append_quality_flag(analysis, "future_report_date")

    if analysis.get("has_reported") is False:
        analysis["eps_actual"] = None
        analysis["eps_surprise_pct"] = None
        analysis["revenue_actual"] = None
        analysis["revenue_surprise_pct"] = None
        analysis["price_reaction_pct"] = None
    else:
        if analysis.get("eps_actual") is None:
            _append_quality_flag(analysis, "missing_actual_eps")
        if analysis.get("revenue_actual") is None:
            _append_quality_flag(analysis, "missing_actual_revenue")

        if analysis.get("eps_actual") is None and analysis.get("revenue_actual") is None:
            confidence = min(confidence, 0.45)

        if analysis.get("eps_actual") is not None:
            analysis["eps_surprise_pct"] = _recompute_surprise(
                analysis.get("eps_actual"), analysis.get("eps_estimate")
            )

        if analysis.get("revenue_actual") is not None:
            analysis["revenue_surprise_pct"] = _recompute_surprise(
                analysis.get("revenue_actual"), analysis.get("revenue_estimate")
            )

    guidance_summary = analysis.get("guidance_summary")
    if not isinstance(guidance_summary, str) or not guidance_summary.strip():
        _append_quality_flag(analysis, "missing_guidance")

    if analysis.get("price_reaction_pct") is not None and not _has_field_citation(citations, "price_reaction_pct"):
        _append_quality_flag(analysis, "price_reaction_unverified")

    if not citations:
        confidence = min(confidence, 0.4)

    analysis["confidence_score"] = _clamp_confidence(confidence, 0.5)

    if analysis["confidence_score"] >= 0.75:
        analysis["data_completeness"] = "high"
    elif analysis["confidence_score"] >= 0.5:
        analysis["data_completeness"] = "medium"
    else:
        analysis["data_completeness"] = "low"

    return analysis


async def run_analysis_streaming(
    db: AsyncSession, ticker: str, quarter: str
) -> AsyncGenerator[tuple[str, dict], None]:
    from app.services.cache import get_cached_analysis_redis, set_cached_analysis_redis

    yield ("status", {"step": "cache", "message": "Starting analysis..."})

    cached = await get_cached_analysis_redis(ticker, quarter)
    if cached:
        yield ("result", cached)
        return

    event_query = (
        select(EarningsEvent)
        .where(
            EarningsEvent.ticker == ticker.upper(),
            EarningsEvent.fiscal_quarter == quarter,
        )
        .order_by(EarningsEvent.report_date.desc())
        .limit(1)
    )
    event_result = await db.execute(event_query)
    event = event_result.scalar_one_or_none()

    if not event:
        fallback_query = (
            select(EarningsEvent)
            .where(EarningsEvent.ticker == ticker.upper())
            .order_by(EarningsEvent.report_date.desc())
            .limit(1)
        )
        fallback_result = await db.execute(fallback_query)
        event = fallback_result.scalar_one_or_none()

    event_context = None
    company_name = None
    if event:
        company_name = event.company_name
        event_context = {
            "company_name": event.company_name,
            "report_date": event.report_date.isoformat() if event.report_date else None,
            "eps_estimate": float(event.eps_estimate) if event.eps_estimate is not None else None,
            "revenue_estimate": float(event.revenue_estimate) if event.revenue_estimate is not None else None,
            "fiscal_quarter": event.fiscal_quarter,
        }

    yield ("status", {"step": "search", "message": "Searching for earnings data..."})
    search_results = await search_earnings_report(ticker, quarter, company_name=company_name)
    logger.info("Search results for %s %s: %d chars", ticker, quarter, len(search_results))

    yield ("status", {"step": "analyze", "message": "Reading articles & analyzing with AI..."})
    analysis = await analyze_earnings(ticker, search_results, event_context=event_context)
    analysis = _apply_quality_gate(analysis, event_context)
    logger.info("Analysis result for %s %s: has_reported=%s", ticker, quarter, analysis.get("has_reported"))

    if "error" in analysis:
        yield ("error", analysis)
        return

    yield ("status", {"step": "save", "message": "Saving results..."})

    if event:
        earnings_analysis = EarningsAnalysis(
            earnings_event_id=event.id,
            eps_estimate=analysis.get("eps_estimate"),
            eps_actual=analysis.get("eps_actual"),
            eps_surprise_pct=analysis.get("eps_surprise_pct"),
            revenue_estimate=analysis.get("revenue_estimate"),
            revenue_actual=analysis.get("revenue_actual"),
            revenue_surprise_pct=analysis.get("revenue_surprise_pct"),
            guidance_summary=analysis.get("guidance_summary"),
            sentiment=analysis.get("sentiment"),
            sentiment_score=analysis.get("sentiment_score"),
            price_reaction_pct=analysis.get("price_reaction_pct"),
            raw_analysis=analysis,
            analyzed_at=datetime.utcnow(),
        )
        db.add(earnings_analysis)
        await db.commit()
        await db.refresh(earnings_analysis)
        analysis["id"] = earnings_analysis.id
        analysis["earnings_event_id"] = event.id

    analysis["ticker"] = ticker.upper()
    analysis["quarter"] = quarter
    analysis.setdefault("has_reported", True)

    await set_cached_analysis_redis(ticker, quarter, analysis)

    yield ("result", analysis)


async def get_cached_analysis(
    db: AsyncSession, ticker: str, quarter: str | None = None
) -> dict | None:
    query = (
        select(EarningsAnalysis)
        .join(EarningsEvent)
        .where(EarningsEvent.ticker == ticker.upper())
    )

    if quarter is not None:
        query = query.where(EarningsEvent.fiscal_quarter == quarter)

    query = query.order_by(EarningsAnalysis.analyzed_at.desc()).limit(1)

    result = await db.execute(query)
    analysis = result.scalar_one_or_none()

    if not analysis:
        return None

    has_reported = True
    if analysis.raw_analysis and isinstance(analysis.raw_analysis, dict):
        has_reported = analysis.raw_analysis.get("has_reported", True)

    stale = False
    if not has_reported and analysis.analyzed_at:
        from app.services.cache import ANALYSIS_UNREPORTED_TTL
        age = datetime.utcnow() - analysis.analyzed_at
        stale = age >= timedelta(seconds=ANALYSIS_UNREPORTED_TTL)

    return {
        "id": analysis.id,
        "earnings_event_id": analysis.earnings_event_id,
        "ticker": ticker.upper(),
        "has_reported": has_reported,
        "stale": stale,
        "eps_estimate": analysis.eps_estimate,
        "eps_actual": analysis.eps_actual,
        "eps_surprise_pct": analysis.eps_surprise_pct,
        "revenue_estimate": analysis.revenue_estimate,
        "revenue_actual": analysis.revenue_actual,
        "revenue_surprise_pct": analysis.revenue_surprise_pct,
        "guidance_summary": analysis.guidance_summary,
        "sentiment": analysis.sentiment.value if analysis.sentiment else None,
        "sentiment_score": analysis.sentiment_score,
        "price_reaction_pct": analysis.price_reaction_pct,
        "financial_highlights": analysis.raw_analysis.get("financial_highlights") if isinstance(analysis.raw_analysis, dict) else None,
        "confidence_score": analysis.raw_analysis.get("confidence_score") if isinstance(analysis.raw_analysis, dict) else None,
        "data_completeness": analysis.raw_analysis.get("data_completeness") if isinstance(analysis.raw_analysis, dict) else None,
        "source_count": analysis.raw_analysis.get("source_count") if isinstance(analysis.raw_analysis, dict) else 0,
        "citations": analysis.raw_analysis.get("citations") if isinstance(analysis.raw_analysis, dict) else [],
        "quality_flags": analysis.raw_analysis.get("quality_flags") if isinstance(analysis.raw_analysis, dict) else [],
        "raw_analysis": analysis.raw_analysis,
        "analyzed_at": analysis.analyzed_at.isoformat() if analysis.analyzed_at else None,
    }
