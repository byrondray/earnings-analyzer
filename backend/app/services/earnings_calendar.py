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
FMP_HISTORICAL_EARNINGS_URL = "https://financialmodelingprep.com/api/v3/historical/earning_calendar"


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
            logger.warning(
                "Alpha Vantage request failed with status %d: %s",
                resp.status_code,
                resp.text[:200] if resp.text else "no response body",
            )
            return []

        text = resp.text
        if not text or text.startswith("{"):
            logger.warning("Alpha Vantage returned non-CSV response (likely error or rate limit)")
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
        logger.info("Alpha Vantage returned %d earnings entries", len(results))
        return results


NASDAQ_EARNINGS_URL = "https://api.nasdaq.com/api/calendar/earnings"
NASDAQ_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "Origin": "https://www.nasdaq.com",
    "Referer": "https://www.nasdaq.com/",
}


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


_NASDAQ_FETCH_CONCURRENCY = 3


async def _fetch_nasdaq_rows_for_date(
    client: httpx.AsyncClient, sem: asyncio.Semaphore, d: date
) -> list[dict]:
    async with sem:
        rows = []
        for attempt in range(2):
            try:
                resp = await client.get(
                    NASDAQ_EARNINGS_URL,
                    params={
                        "date": d.isoformat(),
                        "offset": 0,
                        "limit": 1000,
                    },
                    headers=NASDAQ_HEADERS,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    rows = data.get("data", {}).get("rows") or []
                    break
                logger.warning(
                    "Nasdaq earnings fetch failed for %s (status=%d, attempt=%d)",
                    d,
                    resp.status_code,
                    attempt + 1,
                )
            except Exception as e:
                logger.warning(
                    "Nasdaq earnings fetch exception for %s (attempt=%d): %s",
                    d,
                    attempt + 1,
                    e,
                )
            if attempt == 0:
                await asyncio.sleep(0.35)

    results = []
    for row in rows:
        symbol = row.get("symbol", "")
        if not symbol:
            continue
        results.append({
            "symbol": symbol,
            "companyName": row.get("name", symbol),
            "date": d.isoformat(),
            "time": "",
            "fiscalDateEnding": _normalize_fiscal_quarter(row.get("fiscalQuarterEnding")),
            "epsEstimated": _parse_nasdaq_eps_forecast(row.get("epsForecast")),
            "marketCap": _parse_nasdaq_market_cap(row.get("marketCap")),
        })
    return results


async def _fetch_historical_earnings_nasdaq(
    start: date, end: date
) -> list[dict]:
    dates = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            dates.append(current)
        current += timedelta(days=1)

    sem = asyncio.Semaphore(_NASDAQ_FETCH_CONCURRENCY)
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, http2=True) as client:
        per_date_results = await asyncio.gather(
            *(_fetch_nasdaq_rows_for_date(client, sem, d) for d in dates)
        )

    results = [row for rows in per_date_results for row in rows]
    logger.info(
        "Nasdaq historical fetch completed for %s..%s with %d rows",
        start,
        end,
        len(results),
    )
    return results


async def _fetch_historical_earnings_fmp(start: date, end: date) -> list[dict]:
    settings = get_settings()
    params = {
        "from": start.isoformat(),
        "to": end.isoformat(),
    }
    if settings.FMP_API_KEY:
        params["apikey"] = settings.FMP_API_KEY
    else:
        params["apikey"] = "demo"
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(FMP_HISTORICAL_EARNINGS_URL, params=params)
        if resp.status_code != 200:
            logger.warning("FMP historical earnings fetch failed with status %d", resp.status_code)
            return []

        payload = resp.json()
        if not isinstance(payload, list):
            logger.warning("FMP historical earnings response was not a list")
            return []

        results = []
        for row in payload:
            symbol = (row.get("symbol") or "").strip()
            report_date = (row.get("date") or "").strip()
            if not symbol or not report_date:
                continue
            try:
                dt = date.fromisoformat(report_date)
            except ValueError:
                continue
            if dt < start or dt > end:
                continue

            company_name = (
                row.get("company")
                or row.get("companyName")
                or symbol
            )
            results.append({
                "symbol": symbol,
                "companyName": company_name,
                "date": dt.isoformat(),
                "time": row.get("time") or "",
                "fiscalDateEnding": row.get("fiscalDateEnding"),
                "epsEstimated": _safe_float(str(row.get("epsEstimated"))) if row.get("epsEstimated") is not None else None,
            })

        logger.info(
            "FMP historical fetch completed for %s..%s with %d rows",
            start,
            end,
            len(results),
        )
        return results
    except Exception as e:
        logger.warning("FMP historical fetch failed for %s..%s: %s", start, end, e)
        return []


def _safe_float(val: str | None) -> float | None:
    if not val or val.strip() == "":
        return None
    try:
        return float(val)
    except ValueError:
        return None


async def upsert_earnings_events(
    db: AsyncSession, events_data: list[dict], return_events: bool = True
) -> list[EarningsEvent]:
    if not events_data:
        return []

    rows = []
    dropped = 0
    truncated = 0
    for item in events_data:
        symbol = (item.get("symbol") or "").strip().upper()
        if not symbol or not item.get("date") or len(symbol) > 10:
            dropped += 1
            continue
        company_name = item.get("companyName", symbol)
        if len(company_name) > 255:
            truncated += 1
        row = {
            "ticker": symbol,
            "company_name": company_name[:255],
            "report_date": date.fromisoformat(item["date"]),
            "report_time": _map_report_time(item.get("time")),
            "fiscal_quarter": item.get("fiscalDateEnding"),
            "eps_estimate": item.get("epsEstimated"),
            "revenue_estimate": item.get("revenueEstimated"),
        }
        if item.get("marketCap") is not None:
            row["market_cap"] = item["marketCap"]
        rows.append(row)

    if dropped:
        logger.warning("upsert_earnings_events: dropped %d of %d rows (missing/invalid symbol or date)", dropped, len(events_data))
    if truncated:
        logger.warning("upsert_earnings_events: truncated company_name for %d rows exceeding 255 chars", truncated)

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

    if not return_events:
        return []

    min_report_date = min(r["report_date"] for r in rows)
    max_report_date = max(r["report_date"] for r in rows)
    query = select(EarningsEvent).where(
        EarningsEvent.report_date >= min_report_date,
        EarningsEvent.report_date <= max_report_date,
    )
    result = await db.execute(query)
    return list(result.scalars().all())


logger = logging.getLogger(__name__)

_ENRICH_TIMEOUT = 30


async def _fetch_nasdaq_market_caps_for_date(client: httpx.AsyncClient, d: date) -> dict[str, float]:
    caps: dict[str, float] = {}
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
    return caps


async def _enrich_market_caps_from_nasdaq(
    db: AsyncSession, events: list[EarningsEvent]
) -> list[EarningsEvent]:
    needs_cap = [e for e in events if e.market_cap is None]
    if not needs_cap:
        return events

    dates_to_fetch = [d for d in dict.fromkeys(e.report_date for e in needs_cap) if d.weekday() < 5]
    logger.info("Enriching market caps from Nasdaq for %d dates", len(dates_to_fetch))

    caps: dict[str, float] = {}
    async with httpx.AsyncClient(timeout=15.0) as client:
        results = await asyncio.gather(
            *(_fetch_nasdaq_market_caps_for_date(client, d) for d in dates_to_fetch)
        )
        for result in results:
            caps.update(result)

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
    from app.services.cache import should_search_alpha_vantage, mark_alpha_vantage_searched

    upper_ticker = ticker.upper().strip()

    if await should_search_alpha_vantage(upper_ticker):
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
                        await upsert_earnings_events(db, av_results, return_events=False)
            await mark_alpha_vantage_searched(upper_ticker)
        except Exception as e:
            logger.warning("Alpha Vantage search_ticker failed for %s: %s", upper_ticker, e)
    else:
        logger.debug("Skipping Alpha Vantage search for %s (cached within TTL)", upper_ticker)

    query = (
        select(EarningsEvent)
        .where(EarningsEvent.ticker == upper_ticker)
        .order_by(EarningsEvent.report_date)
    )
    result = await db.execute(query)
    return list(result.scalars().all())


_av_sync_task: "asyncio.Task | None" = None


async def _do_alpha_vantage_sync():
    from app.services.cache import mark_alpha_vantage_synced
    from app.db.database import get_session_factory

    logger.info("Syncing earnings data from Alpha Vantage...")
    try:
        all_data = await fetch_all_earnings_from_alpha_vantage()
        if all_data:
            factory = get_session_factory()
            async with factory() as session:
                await upsert_earnings_events(session, all_data)
            logger.info("Successfully synced %d events from Alpha Vantage", len(all_data))
            await mark_alpha_vantage_synced()
        else:
            logger.warning("Alpha Vantage returned no earnings data")
            await mark_alpha_vantage_synced(ttl=300)
    except Exception as e:
        logger.error("Alpha Vantage sync failed: %s", e, exc_info=True)


def _trigger_alpha_vantage_sync_background():
    """Kick off an Alpha Vantage sync without blocking the caller.

    Uses its own DB session (not the request-scoped one) since the task
    keeps running after the triggering request/session has closed.
    """
    global _av_sync_task
    if _av_sync_task is not None and not _av_sync_task.done():
        return
    _av_sync_task = asyncio.create_task(_do_alpha_vantage_sync())


async def _sync_alpha_vantage_data(db: AsyncSession):
    from app.services.cache import should_sync_alpha_vantage, mark_alpha_vantage_synced

    if not await should_sync_alpha_vantage():
        logger.debug("Skipping Alpha Vantage sync (cached within TTL)")
        return

    # Mark as synced immediately so concurrent requests don't all trigger
    # their own background sync while this one is in flight.
    await mark_alpha_vantage_synced(ttl=300)
    _trigger_alpha_vantage_sync_background()


async def get_week_earnings(
    db: AsyncSession, target_date: date
) -> list[EarningsEvent]:
    monday, friday = week_bounds(target_date)
    # Include full calendar week (Sunday through Saturday) for earnings data
    week_start = monday
    week_end = friday + timedelta(days=2)  # Include Saturday and Sunday

    await _sync_alpha_vantage_data(db)

    query = select(EarningsEvent).where(
        EarningsEvent.report_date >= week_start,
        EarningsEvent.report_date <= week_end,
    ).order_by(EarningsEvent.report_date, EarningsEvent.ticker)
    result = await db.execute(query)
    events = list(result.scalars().all())

    is_current_week = week_start <= date.today() <= week_end
    if is_current_week and len(events) <= 1:
        logger.warning(
            "Current week has sparse earnings data (%d events), trying Nasdaq fallback",
            len(events),
        )
        try:
            nasdaq_data = await _fetch_historical_earnings_nasdaq(week_start, week_end)
            if nasdaq_data:
                await upsert_earnings_events(db, nasdaq_data)
                result = await db.execute(query)
                events = list(result.scalars().all())
                logger.info(
                    "Nasdaq fallback upserted %d rows; current week now has %d events",
                    len(nasdaq_data),
                    len(events),
                )
        except Exception as e:
            logger.warning("Nasdaq current-week fallback failed: %s", e)

    if not events and week_end < date.today():
        try:
            nasdaq_data = await _fetch_historical_earnings_nasdaq(week_start, week_end)
            if nasdaq_data:
                events = await upsert_earnings_events(db, nasdaq_data)
                logger.info("Fetched %d historical events from Nasdaq for %s", len(events), week_start)
            else:
                logger.warning(
                    "No Nasdaq historical rows for week %s..%s",
                    week_start,
                    week_end,
                )
                fmp_data = await _fetch_historical_earnings_fmp(week_start, week_end)
                if fmp_data:
                    events = await upsert_earnings_events(db, fmp_data)
                    logger.info("Fetched %d historical events from FMP for %s", len(events), week_start)
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


_RECENT_FALLBACK_LIMIT = 300
_RECENT_FALLBACK_WINDOW_DAYS = 6
_RECENT_FALLBACK_MIN_EVENTS = 6


async def fetch_recent_fallback_events(
    db: AsyncSession, before_date: date, min_events: int = _RECENT_FALLBACK_MIN_EVENTS
) -> tuple[list[EarningsEvent], date, date]:
    """Find the most recent window of earnings events before `before_date`.

    Used when the requested week has no data (e.g. sparse historical
    coverage), to fall back to whatever the most recent reported week was.
    Returns (events, window_start, window_end).
    """
    recent_cutoff = before_date - timedelta(days=1)
    recent_query = (
        select(EarningsEvent)
        .where(EarningsEvent.report_date <= recent_cutoff)
        .order_by(
            EarningsEvent.report_date.desc(),
            EarningsEvent.market_cap.desc(),
            EarningsEvent.ticker,
        )
        .limit(_RECENT_FALLBACK_LIMIT)
    )
    recent_result = await db.execute(recent_query)
    recent_events = list(recent_result.scalars().all())
    if not recent_events:
        return [], before_date, before_date

    recent_end = recent_events[0].report_date
    recent_start = recent_end - timedelta(days=_RECENT_FALLBACK_WINDOW_DAYS)
    window_events = [
        e for e in recent_events
        if recent_start <= e.report_date <= recent_end
    ]
    if len(window_events) >= min_events:
        return window_events, recent_start, recent_end
    return recent_events, recent_start, recent_end
