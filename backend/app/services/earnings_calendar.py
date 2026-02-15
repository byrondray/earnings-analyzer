from datetime import date, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import EarningsEvent, ReportTime

FMP_BASE = "https://financialmodelingprep.com/api/v3"


def week_bounds(d: date) -> tuple[date, date]:
    monday = d - timedelta(days=d.weekday())
    friday = monday + timedelta(days=4)
    return monday, friday


def _map_report_time(raw: str | None) -> ReportTime:
    if not raw:
        return ReportTime.UNKNOWN
    lower = raw.lower()
    if "bmo" in lower or "before" in lower:
        return ReportTime.PRE_MARKET
    if "amc" in lower or "after" in lower:
        return ReportTime.POST_MARKET
    return ReportTime.UNKNOWN


async def fetch_earnings_from_fmp(
    start: date, end: date
) -> list[dict]:
    settings = get_settings()
    url = f"{FMP_BASE}/earning_calendar"
    params = {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "apikey": settings.FMP_API_KEY,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


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


async def get_week_earnings(
    db: AsyncSession, target_date: date
) -> list[EarningsEvent]:
    monday, friday = week_bounds(target_date)

    fmp_data = await fetch_earnings_from_fmp(monday, friday)
    events = await upsert_earnings_events(db, fmp_data)

    if not events:
        query = select(EarningsEvent).where(
            EarningsEvent.report_date >= monday,
            EarningsEvent.report_date <= friday,
        ).order_by(EarningsEvent.report_date, EarningsEvent.ticker)
        result = await db.execute(query)
        events = list(result.scalars().all())

    return sorted(events, key=lambda e: (e.report_date, e.ticker))
