from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.database import get_db
from app.db.models import ReportTime
from app.services.earnings_calendar import get_week_earnings, search_ticker, week_bounds

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

    return WeekEarningsResponse(
        week_start=monday,
        week_end=friday,
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

    return WeekEarningsResponse(
        week_start=monday,
        week_end=friday,
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

    return WeekEarningsResponse(
        week_start=monday,
        week_end=friday,
        events=[_to_response(e) for e in events],
    )
