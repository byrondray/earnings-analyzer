from collections.abc import AsyncGenerator
from datetime import datetime
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EarningsAnalysis, EarningsEvent
from app.mcp_server.tools.web_search import search_earnings_report
from app.mcp_server.tools.analyze import analyze_earnings

logger = logging.getLogger(__name__)


async def run_analysis_streaming(
    db: AsyncSession, ticker: str, quarter: str
) -> AsyncGenerator[tuple[str, dict], None]:
    from app.services.cache import get_cached_analysis_redis, set_cached_analysis_redis

    yield ("status", {"step": "cache", "message": "Checking cache..."})

    cached = await get_cached_analysis_redis(ticker, quarter)
    if cached:
        yield ("result", cached)
        return

    event_query = (
        select(EarningsEvent)
        .where(EarningsEvent.ticker == ticker.upper())
        .order_by(EarningsEvent.report_date.desc())
        .limit(1)
    )
    event_result = await db.execute(event_query)
    event = event_result.scalar_one_or_none()

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
    db: AsyncSession, ticker: str
) -> dict | None:
    query = (
        select(EarningsAnalysis)
        .join(EarningsEvent)
        .where(EarningsEvent.ticker == ticker.upper())
        .order_by(EarningsAnalysis.analyzed_at.desc())
        .limit(1)
    )
    result = await db.execute(query)
    analysis = result.scalar_one_or_none()

    if not analysis:
        return None

    has_reported = True
    if analysis.raw_analysis and isinstance(analysis.raw_analysis, dict):
        has_reported = analysis.raw_analysis.get("has_reported", True)

    return {
        "id": analysis.id,
        "earnings_event_id": analysis.earnings_event_id,
        "ticker": ticker.upper(),
        "has_reported": has_reported,
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
        "raw_analysis": analysis.raw_analysis,
        "analyzed_at": analysis.analyzed_at.isoformat() if analysis.analyzed_at else None,
    }
