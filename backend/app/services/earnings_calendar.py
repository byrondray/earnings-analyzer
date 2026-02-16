import asyncio
import logging
from datetime import date, timedelta
import csv
import io

import httpx
from sqlalchemy import func, select
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


async def fetch_all_earnings_from_alpha_vantage() -> list[dict]:
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
                date.fromisoformat(row.get("reportDate", ""))
            except ValueError:
                continue
            results.append({
                "symbol": row.get("symbol", ""),
                "companyName": row.get("name", row.get("symbol", "")),
                "date": row.get("reportDate", ""),
                "time": row.get("timeOfTheDay", ""),
                "fiscalDateEnding": row.get("fiscalDateEnding"),
                "epsEstimated": _safe_float(row.get("estimate")),
            })
        return results


NASDAQ_EARNINGS_URL = "https://api.nasdaq.com/api/calendar/earnings"
NASDAQ_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _normalize_fiscal_quarter(raw: str | None) -> str | None:
    """Convert Nasdaq format 'Dec/2025' to ISO format '2025-12-31'."""
    if not raw:
        return None
    if "/" in raw:
        parts = raw.split("/")
        if len(parts) == 2:
            month_str, year_str = parts
            month = _MONTH_MAP.get(month_str.strip().lower()[:3])
            if month and year_str.strip().isdigit():
                import calendar
                year = int(year_str.strip())
                last_day = calendar.monthrange(year, month)[1]
                return f"{year}-{month:02d}-{last_day:02d}"
    return raw


def _parse_nasdaq_market_cap(raw: str | None) -> float | None:
    if not raw or raw.strip() == "" or raw.strip() == "N/A":
        return None
    cleaned = raw.replace("$", "").replace(",", "").strip()
    return _safe_float(cleaned)


def _parse_nasdaq_eps_forecast(raw: str | None) -> float | None:
    if not raw or raw.strip() == "":
        return None
    cleaned = raw.replace("$", "").replace(",", "").strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    return _safe_float(cleaned)


async def _fetch_historical_earnings_nasdaq(
    start: date, end: date
) -> list[dict]:
    results = []
    async with httpx.AsyncClient(timeout=15.0) as client:
        current = start
        while current <= end:
            if current.weekday() >= 5:
                current += timedelta(days=1)
                continue
            try:
                resp = await client.get(
                    NASDAQ_EARNINGS_URL,
                    params={"date": current.isoformat()},
                    headers=NASDAQ_HEADERS,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    rows = data.get("data", {}).get("rows") or []
                    for row in rows:
                        symbol = row.get("symbol", "")
                        if not symbol:
                            continue
                        results.append({
                            "symbol": symbol,
                            "companyName": row.get("name", symbol),
                            "date": current.isoformat(),
                            "time": "",
                            "fiscalDateEnding": _normalize_fiscal_quarter(row.get("fiscalQuarterEnding")),
                            "epsEstimated": _parse_nasdaq_eps_forecast(row.get("epsForecast")),
                            "marketCap": _parse_nasdaq_market_cap(row.get("marketCap")),
                        })
            except Exception:
                pass
            current += timedelta(days=1)
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
        row = {
            "ticker": item["symbol"],
            "company_name": item.get("companyName", item["symbol"]),
            "report_date": date.fromisoformat(item["date"]),
            "report_time": _map_report_time(item.get("time")),
            "fiscal_quarter": item.get("fiscalDateEnding"),
            "eps_estimate": item.get("epsEstimated"),
            "revenue_estimate": item.get("revenueEstimated"),
        }
        if item.get("marketCap") is not None:
            row["market_cap"] = item["marketCap"]
        rows.append(row)

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
            "market_cap": func.coalesce(stmt.excluded.market_cap, EarningsEvent.market_cap),
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

_ENRICH_TIMEOUT = 30


async def _enrich_market_caps_from_nasdaq(
    db: AsyncSession, events: list[EarningsEvent]
) -> list[EarningsEvent]:
    needs_cap = [e for e in events if e.market_cap is None]
    if not needs_cap:
        return events

    dates_to_fetch = list(dict.fromkeys(e.report_date for e in needs_cap))
    logger.info("Enriching market caps from Nasdaq for %d dates", len(dates_to_fetch))

    caps: dict[str, float] = {}
    async with httpx.AsyncClient(timeout=15.0) as client:
        for d in dates_to_fetch:
            if d.weekday() >= 5:
                continue
            try:
                resp = await client.get(
                    NASDAQ_EARNINGS_URL,
                    params={"date": d.isoformat()},
                    headers=NASDAQ_HEADERS,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for row in data.get("data", {}).get("rows") or []:
                        symbol = row.get("symbol", "")
                        mcap = _parse_nasdaq_market_cap(row.get("marketCap"))
                        if symbol and mcap is not None:
                            caps[symbol] = mcap
            except Exception as e:
                logger.warning("Nasdaq market cap fetch failed for %s: %s", d, e)

    updated = 0
    for event in events:
        cap = caps.get(event.ticker)
        if cap is not None and event.market_cap != cap:
            event.market_cap = cap
            updated += 1

    logger.info("Nasdaq enrichment: got %d caps, updated %d events", len(caps), updated)

    if updated:
        try:
            await db.commit()
        except Exception:
            await db.rollback()

    return events


async def search_ticker(
    db: AsyncSession, ticker: str
) -> list[EarningsEvent]:
    upper_ticker = ticker.upper().strip()

    try:
        settings = get_settings()
        params = {
            "function": "EARNINGS_CALENDAR",
            "horizon": "3month",
            "symbol": upper_ticker,
            "apikey": settings.ALPHA_VANTAGE_API_KEY,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(ALPHA_VANTAGE_BASE, params=params)
            if resp.status_code == 200 and resp.text and not resp.text.startswith("{"):
                reader = csv.DictReader(io.StringIO(resp.text))
                av_results = []
                for row in reader:
                    av_results.append({
                        "symbol": row.get("symbol", ""),
                        "companyName": row.get("name", row.get("symbol", "")),
                        "date": row.get("reportDate", ""),
                        "time": row.get("timeOfTheDay", ""),
                        "fiscalDateEnding": row.get("fiscalDateEnding"),
                        "epsEstimated": _safe_float(row.get("estimate")),
                    })
                if av_results:
                    await upsert_earnings_events(db, av_results)
    except Exception:
        pass

    query = (
        select(EarningsEvent)
        .where(EarningsEvent.ticker == upper_ticker)
        .order_by(EarningsEvent.report_date)
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def _sync_alpha_vantage_data(db: AsyncSession):
    from app.services.cache import should_sync_alpha_vantage, mark_alpha_vantage_synced

    if not await should_sync_alpha_vantage():
        return

    try:
        all_data = await fetch_all_earnings_from_alpha_vantage()
        if all_data:
            await upsert_earnings_events(db, all_data)
            logger.info("Synced %d events from Alpha Vantage", len(all_data))
        await mark_alpha_vantage_synced()
    except Exception as e:
        logger.warning("Alpha Vantage sync failed: %s", e)


async def get_week_earnings(
    db: AsyncSession, target_date: date
) -> list[EarningsEvent]:
    monday, friday = week_bounds(target_date)

    await _sync_alpha_vantage_data(db)

    query = select(EarningsEvent).where(
        EarningsEvent.report_date >= monday,
        EarningsEvent.report_date <= friday,
    ).order_by(EarningsEvent.report_date, EarningsEvent.ticker)
    result = await db.execute(query)
    events = list(result.scalars().all())

    if not events and friday < date.today():
        try:
            nasdaq_data = await _fetch_historical_earnings_nasdaq(monday, friday)
            if nasdaq_data:
                events = await upsert_earnings_events(db, nasdaq_data)
                logger.info("Fetched %d historical events from Nasdaq for %s", len(events), monday)
        except Exception as e:
            logger.warning("Nasdaq historical fetch failed: %s", e)

    try:
        events = await _enrich_market_caps_from_nasdaq(db, events)
    except Exception as e:
        logger.warning("Market cap enrichment failed: %s", e)

    return sorted(
        events,
        key=lambda e: (e.report_date, -(e.market_cap or 0), e.ticker),
    )
