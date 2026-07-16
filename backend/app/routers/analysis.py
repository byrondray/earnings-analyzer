import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db.database import get_db
from app.rate_limit import limiter
from app.services.analysis import run_analysis_streaming, get_cached_analysis
from app.validation import validate_ticker as _validate_ticker, validate_quarter as _validate_quarter

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/{ticker}")
@limiter.limit("10/hour")
async def analyze_ticker(
    request: Request,
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
@limiter.limit("60/minute")
async def get_analysis(
    request: Request,
    ticker: str,
    quarter: str | None = Query(default=None, description="Fiscal quarter, e.g. Q4-2025"),
    db: AsyncSession = Depends(get_db),
):
    clean_ticker = _validate_ticker(ticker)
    clean_quarter = _validate_quarter(quarter) if quarter is not None else None
    result = await get_cached_analysis(db, clean_ticker, clean_quarter)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No analysis found for {clean_ticker} {clean_quarter}"
                if clean_quarter
                else f"No analysis found for {clean_ticker}"
            ),
        )
    return result
