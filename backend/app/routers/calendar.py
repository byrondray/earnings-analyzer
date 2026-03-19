import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
import httpx

from app.config import get_settings
from app.db.database import get_db
from app.db.models import EarningsEvent, ReportTime
from app.services.cache import (
    get_cached_highlights, set_cached_highlights,
    get_cached_sparkline, set_cached_sparkline,
)
from app.services.earnings_calendar import (
    get_week_earnings,
    search_ticker,
    week_bounds,
    _fetch_historical_earnings_nasdaq,
    _fetch_historical_earnings_fmp,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


def _to_response(e: object) -> "EarningsEventResponse":
    return EarningsEventResponse(
        id=e.id,
        ticker=e.ticker,
        company_name=e.company_name,
        report_date=e.report_date,
        report_time=e.report_time.value if isinstance(e.report_time, ReportTime) else str(e.report_time),
        fiscal_quarter=e.fiscal_quarter,
        eps_estimate=e.eps_estimate,
        revenue_estimate=e.revenue_estimate,
        market_cap=e.market_cap,
    )


class EarningsEventResponse(BaseModel):
    id: int
    ticker: str
    company_name: str
    report_date: date
    report_time: str
    fiscal_quarter: str | None
    eps_estimate: float | None
    revenue_estimate: float | None
    market_cap: float | None = None

    model_config = {"from_attributes": True}


class WeekEarningsResponse(BaseModel):
    week_start: date
    week_end: date
    events: list[EarningsEventResponse]


class HighlightsSection(BaseModel):
    week_start: date
    week_end: date
    events: list[EarningsEventResponse]


class HighlightsResponse(BaseModel):
    last_week: HighlightsSection
    this_week: HighlightsSection


class SearchResponse(BaseModel):
    ticker: str
    events: list[EarningsEventResponse]


@router.get("/search", response_model=SearchResponse)
async def search_stock(
    ticker: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    events = await search_ticker(db, ticker)
    return SearchResponse(
        ticker=ticker.upper().strip(),
        events=[_to_response(e) for e in events],
    )


@router.get("/week", response_model=WeekEarningsResponse)
async def get_calendar_week(
    target_date: date = Query(default=None, alias="date"),
    db: AsyncSession = Depends(get_db),
):
    if target_date is None:
        target_date = date.today()

    events = await get_week_earnings(db, target_date)
    monday, friday = week_bounds(target_date)
    week_end = friday + timedelta(days=2)

    return WeekEarningsResponse(
        week_start=monday,
        week_end=week_end,
        events=[_to_response(e) for e in events],
    )


@router.get("/week/next", response_model=WeekEarningsResponse)
async def get_next_week(
    target_date: date = Query(default=None, alias="date"),
    db: AsyncSession = Depends(get_db),
):
    if target_date is None:
        target_date = date.today()
    next_week = target_date + timedelta(weeks=1)
    events = await get_week_earnings(db, next_week)
    monday, friday = week_bounds(next_week)
    week_end = friday + timedelta(days=2)

    return WeekEarningsResponse(
        week_start=monday,
        week_end=week_end,
        events=[_to_response(e) for e in events],
    )


@router.get("/week/prev", response_model=WeekEarningsResponse)
async def get_prev_week(
    target_date: date = Query(default=None, alias="date"),
    db: AsyncSession = Depends(get_db),
):
    if target_date is None:
        target_date = date.today()
    prev_week = target_date - timedelta(weeks=1)
    events = await get_week_earnings(db, prev_week)
    monday, friday = week_bounds(prev_week)
    week_end = friday + timedelta(days=2)

    return WeekEarningsResponse(
        week_start=monday,
        week_end=week_end,
        events=[_to_response(e) for e in events],
    )


_HIGHLIGHTS_LIMIT = 10


@router.get("/highlights", response_model=HighlightsResponse)
async def get_highlights(
    db: AsyncSession = Depends(get_db),
    refresh: bool = False,
):
    if not refresh:
        cached = await get_cached_highlights()
        if cached:
            try:
                cached_resp = HighlightsResponse(**cached)
                if len(cached_resp.this_week.events) > 1:
                    return cached_resp
                logger.warning(
                    "Ignoring sparse cached highlights (this_week events=%d), recomputing",
                    len(cached_resp.this_week.events),
                )
            except Exception:
                logger.warning("Cached highlights payload invalid; recomputing")
    try:
        today = date.today()
        anchor = today
        if anchor.weekday() >= 5:
            anchor = anchor + timedelta(days=(7 - anchor.weekday()))

        last_mon, last_fri = week_bounds(anchor - timedelta(weeks=1))
        this_mon, this_fri = week_bounds(anchor)
        last_sun = last_fri + timedelta(days=2)
        this_sun = this_fri + timedelta(days=2)

        last_events = await get_week_earnings(db, last_mon)
        this_events = await get_week_earnings(db, this_mon)

        if not last_events:
            recent_cutoff = this_mon - timedelta(days=1)
            recent_query = (
                select(EarningsEvent)
                .where(EarningsEvent.report_date <= recent_cutoff)
                .order_by(
                    EarningsEvent.report_date.desc(),
                    EarningsEvent.market_cap.desc(),
                    EarningsEvent.ticker,
                )
                .limit(300)
            )
            recent_result = await db.execute(recent_query)
            recent_events = list(recent_result.scalars().all())

            if recent_events:
                recent_end = recent_events[0].report_date
                recent_start = recent_end - timedelta(days=6)
                window_events = [
                    e for e in recent_events
                    if recent_start <= e.report_date <= recent_end
                ]
                if len(window_events) < _HIGHLIGHTS_LIMIT:
                    window_events = recent_events

                last_events = window_events
                last_mon = recent_start
                last_sun = recent_end
                logger.info(
                    "Last week empty; using recent earnings window %s..%s (%d events)",
                    last_mon,
                    last_sun,
                    len(last_events),
                )

        this_top = sorted(
            this_events, key=lambda e: (-(e.market_cap or 0), e.ticker)
        )[:_HIGHLIGHTS_LIMIT]
        this_keys = {(e.ticker, e.report_date) for e in this_top}
        last_top = sorted(
            [e for e in last_events if (e.ticker, e.report_date) not in this_keys],
            key=lambda e: (-(e.market_cap or 0), e.ticker),
        )[:_HIGHLIGHTS_LIMIT]

        logger.info(
            "Highlights: last_week top tickers=%s, this_week top tickers=%s",
            [(e.ticker, e.market_cap) for e in last_top[:5]],
            [(e.ticker, e.market_cap) for e in this_top[:5]],
        )

        response = HighlightsResponse(
            last_week=HighlightsSection(
                week_start=last_mon,
                week_end=last_sun,
                events=[_to_response(e) for e in last_top],
            ),
            this_week=HighlightsSection(
                week_start=this_mon,
                week_end=this_sun,
                events=[_to_response(e) for e in this_top],
            ),
        )

        await set_cached_highlights(response.model_dump(mode="json"))
        return response
    except Exception:
        logger.exception("Highlights generation failed")
        if not refresh:
            cached = await get_cached_highlights()
            if cached:
                return HighlightsResponse(**cached)

        today = date.today()
        mon, fri = week_bounds(today)
        sun = fri + timedelta(days=2)
        return HighlightsResponse(
            last_week=HighlightsSection(week_start=mon, week_end=sun, events=[]),
            this_week=HighlightsSection(week_start=mon, week_end=sun, events=[]),
        )


@router.get("/sparkline/{ticker}")
async def get_sparkline(ticker: str):
    upper = ticker.upper().strip()

    cached = await get_cached_sparkline(upper)
    if cached is not None:
        return JSONResponse({"ticker": upper, "prices": cached})

    prices = await _fetch_sparkline_yahoo(upper)
    if prices:
        await set_cached_sparkline(upper, prices)
    return JSONResponse({"ticker": upper, "prices": prices})


@router.get("/sparklines")
async def get_sparklines(tickers: list[str] = Query(..., alias="t")):
    result = {}
    to_fetch = []

    for t in tickers:
        upper = t.upper().strip()
        cached = await get_cached_sparkline(upper)
        if cached is not None:
            result[upper] = cached
        else:
            to_fetch.append(upper)

    if to_fetch:
        import asyncio
        tasks = [_fetch_sparkline_yahoo(t) for t in to_fetch]
        fetched = await asyncio.gather(*tasks, return_exceptions=True)
        for t, prices in zip(to_fetch, fetched):
            if isinstance(prices, Exception) or not prices:
                result[t] = []
            else:
                result[t] = prices
                await set_cached_sparkline(t, prices)

    return JSONResponse(result)


@router.get("/debug/source-check")
async def debug_source_check(
    target_date: date = Query(default=None, alias="date"),
):
    if target_date is None:
        target_date = date.today()
    week_start, week_end_base = week_bounds(target_date)
    week_end = week_end_base + timedelta(days=2)

    nasdaq_rows = await _fetch_historical_earnings_nasdaq(week_start, week_end)
    fmp_rows = await _fetch_historical_earnings_fmp(week_start, week_end)

    return JSONResponse({
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "nasdaq_count": len(nasdaq_rows),
        "fmp_count": len(fmp_rows),
        "nasdaq_sample": [r.get("symbol") for r in nasdaq_rows[:5]],
        "fmp_sample": [r.get("symbol") for r in fmp_rows[:5]],
    })


async def _fetch_sparkline_yahoo(ticker: str) -> list[float]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"range": "1mo", "interval": "1d"}
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params, headers=headers)
        data = resp.json()
        closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        return [round(p, 2) for p in closes if p is not None]
    except Exception:
        logger.warning("Yahoo Finance failed for %s, trying Alpha Vantage", ticker)

    settings = get_settings()
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": ticker,
        "outputsize": "compact",
        "apikey": settings.ALPHA_VANTAGE_API_KEY,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://www.alphavantage.co/query", params=params
            )
        data = resp.json()
        ts = data.get("Time Series (Daily)", {})
        if not ts:
            return []
        sorted_dates = sorted(ts.keys())[-30:]
        return [float(ts[d]["4. close"]) for d in sorted_dates]
    except Exception:
        logger.exception("All sparkline sources failed for %s", ticker)
        return []
