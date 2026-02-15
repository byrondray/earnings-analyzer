from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.analysis import run_analysis, get_cached_analysis

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.post("/{ticker}")
async def analyze_ticker(
    ticker: str,
    quarter: str = Query(..., description="Fiscal quarter, e.g. Q4-2025"),
    db: AsyncSession = Depends(get_db),
):
    result = await run_analysis(db, ticker.upper(), quarter)
    if "error" in result:
        raise HTTPException(status_code=502, detail=result["error"])
    return result


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
