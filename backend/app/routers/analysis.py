import json
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db.database import get_db
from app.services.analysis import run_analysis_streaming, get_cached_analysis

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

_TICKER_RE = re.compile(r"^[A-Z]{1,10}$")
_QUARTER_RE = re.compile(r"^Q[1-4]-\d{4}$")


def _validate_ticker(ticker: str) -> str:
    upper = ticker.upper().strip()
    if not _TICKER_RE.match(upper):
        raise HTTPException(status_code=422, detail="Invalid ticker format")
    return upper


def _validate_quarter(quarter: str) -> str:
    q = quarter.strip()
    if not _QUARTER_RE.match(q):
        raise HTTPException(status_code=422, detail="Invalid quarter format, expected Q1-2025")
    return q


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/{ticker}")
async def analyze_ticker(
    ticker: str,
    quarter: str = Query(..., description="Fiscal quarter, e.g. Q4-2025"),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    clean_ticker = _validate_ticker(ticker)
    clean_quarter = _validate_quarter(quarter)

    async def stream():
        async for event_type, payload in run_analysis_streaming(db, clean_ticker, clean_quarter):
            yield _sse_event(event_type, payload)

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/{ticker}")
async def get_analysis(
    ticker: str,
    db: AsyncSession = Depends(get_db),
):
    clean_ticker = _validate_ticker(ticker)
    result = await get_cached_analysis(db, clean_ticker)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No analysis found for {clean_ticker}",
        )
    return result
