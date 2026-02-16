from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EarningsAnalysis, EarningsEvent
from app.mcp_server.tools.web_search import search_earnings_report
from app.mcp_server.tools.analyze import analyze_earnings


async def run_analysis(
    db: AsyncSession, ticker: str, quarter: str
) -> dict:
    search_results = await search_earnings_report(ticker, quarter)
    analysis = await analyze_earnings(ticker, search_results)

    if "error" in analysis:
        return analysis

    event_query = select(EarningsEvent).where(EarningsEvent.ticker == ticker.upper())
    event_result = await db.execute(event_query)
    event = event_result.scalar_one_or_none()

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
    return analysis


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
