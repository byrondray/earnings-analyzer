import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.analysis import run_analysis_streaming, get_cached_analysis

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/{ticker}")
async def analyze_ticker(
    ticker: str,
    quarter: str = Query(..., description="Fiscal quarter, e.g. Q4-2025"),
    db: AsyncSession = Depends(get_db),
):
    async def stream():
        async for event_type, payload in run_analysis_streaming(db, ticker.upper(), quarter):
            yield _sse_event(event_type, payload)

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/{ticker}")
async def get_analysis(
    ticker: str,
    db: AsyncSession = Depends(get_db),
):
    result = await get_cached_analysis(db, ticker.upper())
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No analysis found for {ticker.upper()}",
        )
    return result
