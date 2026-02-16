import asyncio
import logging
from datetime import date, timedelta
import csv
import io

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import EarningsEvent, ReportTime

ALPHA_VANTAGE_BASE = "https://www.alphavantage.co/query"


def week_bounds(d: date) -> tuple[date, date]:
    monday = d - timedelta(days=d.weekday())
    friday = monday + timedelta(days=4)
    return monday, friday


def _map_report_time(raw: str | None) -> ReportTime:
    if not raw:
        return ReportTime.UNKNOWN
    lower = raw.lower()
    if "bmo" in lower or "before" in lower or "pre" in lower:
        return ReportTime.PRE_MARKET
    if "amc" in lower or "after" in lower or "post" in lower:
        return ReportTime.POST_MARKET
    return ReportTime.UNKNOWN


async def fetch_earnings_from_alpha_vantage(
    start: date, end: date
) -> list[dict]:
    settings = get_settings()
    params = {
        "function": "EARNINGS_CALENDAR",
        "horizon": "3month",
        "apikey": settings.ALPHA_VANTAGE_API_KEY,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(ALPHA_VANTAGE_BASE, params=params)
        if resp.status_code != 200:
            return []

        text = resp.text
        if not text or text.startswith("{"):
            return []

        reader = csv.DictReader(io.StringIO(text))
        results = []
        for row in reader:
            try:
                report_date = date.fromisoformat(row.get("reportDate", ""))
            except ValueError:
                continue
            if start <= report_date <= end:
                results.append({
                    "symbol": row.get("symbol", ""),
                    "companyName": row.get("name", row.get("symbol", "")),
                    "date": row.get("reportDate", ""),
                    "time": row.get("timeOfTheDay", ""),
                    "fiscalDateEnding": row.get("fiscalDateEnding"),
                    "epsEstimated": _safe_float(row.get("estimate")),
                })
        return results


def _safe_float(val: str | None) -> float | None:
    if not val or val.strip() == "":
        return None
    try:
        return float(val)
    except ValueError:
        return None


async def upsert_earnings_events(
    db: AsyncSession, events_data: list[dict]
) -> list[EarningsEvent]:
    if not events_data:
        return []

    rows = []
    for item in events_data:
        if not item.get("symbol") or not item.get("date"):
            continue
        rows.append(
            {
                "ticker": item["symbol"],
                "company_name": item.get("companyName", item["symbol"]),
                "report_date": date.fromisoformat(item["date"]),
                "report_time": _map_report_time(item.get("time")),
                "fiscal_quarter": item.get("fiscalDateEnding"),
                "eps_estimate": item.get("epsEstimated"),
                "revenue_estimate": item.get("revenueEstimated"),
            }
        )

    if not rows:
        return []

    stmt = pg_insert(EarningsEvent).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_ticker_report_date",
        set_={
            "company_name": stmt.excluded.company_name,
            "report_time": stmt.excluded.report_time,
            "fiscal_quarter": stmt.excluded.fiscal_quarter,
            "eps_estimate": stmt.excluded.eps_estimate,
            "revenue_estimate": stmt.excluded.revenue_estimate,
        },
    )
    await db.execute(stmt)
    await db.commit()

    query = select(EarningsEvent).where(
        EarningsEvent.report_date >= rows[0]["report_date"],
        EarningsEvent.report_date <= rows[-1]["report_date"],
    )
    result = await db.execute(query)
    return list(result.scalars().all())


logger = logging.getLogger(__name__)

_ENRICH_TIMEOUT = 12
_MAX_ENRICH_TICKERS = 20


async def _enrich_market_caps(
    db: AsyncSession, events: list[EarningsEvent]
) -> list[EarningsEvent]:
    from app.services.market_cap import fetch_market_caps_batch

    needs_cap = [e for e in events if e.market_cap is None]
    tickers = list(dict.fromkeys(e.ticker for e in needs_cap))[:_MAX_ENRICH_TICKERS]

    if not tickers:
        return events

    logger.info("Enriching market caps for %d tickers", len(tickers))
    caps = await asyncio.wait_for(
        fetch_market_caps_batch(tickers), timeout=_ENRICH_TIMEOUT
    )
    logger.info("Market cap enrichment done, got %d values", sum(1 for v in caps.values() if v is not None))

    for event in events:
        cap = caps.get(event.ticker)
        if cap is not None and event.market_cap != cap:
            event.market_cap = cap

    try:
        await db.commit()
    except Exception:
        await db.rollback()

    return events


async def get_week_earnings(
    db: AsyncSession, target_date: date
) -> list[EarningsEvent]:
    monday, friday = week_bounds(target_date)

    try:
        fmp_data = await fetch_earnings_from_alpha_vantage(monday, friday)
        events = await upsert_earnings_events(db, fmp_data)
    except Exception:
        events = []

    if not events:
        query = select(EarningsEvent).where(
            EarningsEvent.report_date >= monday,
            EarningsEvent.report_date <= friday,
        ).order_by(EarningsEvent.report_date, EarningsEvent.ticker)
        result = await db.execute(query)
        events = list(result.scalars().all())

    try:
        events = await _enrich_market_caps(db, events)
    except Exception:
        pass

    return sorted(
        events,
        key=lambda e: (e.report_date, -(e.market_cap or 0), e.ticker),
    )
