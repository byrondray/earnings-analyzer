import logging

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
import httpx

from app.services.cache import get_cached, set_cached

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chart", tags=["chart"])

RANGE_MAP = {
    "1D": ("1d", "5m"),
    "5D": ("5d", "15m"),
    "1M": ("1mo", "1d"),
    "3M": ("3mo", "1d"),
    "6M": ("6mo", "1d"),
    "1Y": ("1y", "1wk"),
    "5Y": ("5y", "1mo"),
}


@router.get("/{ticker}")
async def get_chart_data(
    ticker: str,
    range: str = Query(default="1M", description="Timeframe: 1D, 5D, 1M, 3M, 6M, 1Y, 5Y"),
):
    upper = ticker.upper().strip()
    range_upper = range.upper().strip()

    if range_upper not in RANGE_MAP:
        range_upper = "1M"

    yahoo_range, yahoo_interval = RANGE_MAP[range_upper]
    ttl = 300 if range_upper in ("1D", "5D") else 3600

    cache_key = f"chart:{upper}:{range_upper}"
    cached = await get_cached(cache_key)
    if cached is not None:
        return JSONResponse(cached)

    data = await _fetch_yahoo_chart(upper, yahoo_range, yahoo_interval)
    if data:
        await set_cached(cache_key, data, ttl=ttl)
    return JSONResponse(data)


async def _fetch_yahoo_chart(ticker: str, yrange: str, interval: str) -> dict:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"range": yrange, "interval": interval, "includePrePost": "false"}
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params, headers=headers)
        raw = resp.json()
        result = raw.get("chart", {}).get("result", [])
        if not result:
            return {"ticker": ticker, "points": [], "meta": {}}

        chart = result[0]
        meta = chart.get("meta", {})
        timestamps = chart.get("timestamp", [])
        quote = chart.get("indicators", {}).get("quote", [{}])[0]

        opens = quote.get("open", [])
        highs = quote.get("high", [])
        lows = quote.get("low", [])
        closes = quote.get("close", [])
        volumes = quote.get("volume", [])

        points = []
        for i, ts in enumerate(timestamps):
            c = closes[i] if i < len(closes) else None
            if c is None:
                continue
            points.append({
                "t": ts,
                "o": round(opens[i], 2) if i < len(opens) and opens[i] is not None else None,
                "h": round(highs[i], 2) if i < len(highs) and highs[i] is not None else None,
                "l": round(lows[i], 2) if i < len(lows) and lows[i] is not None else None,
                "c": round(c, 2),
                "v": volumes[i] if i < len(volumes) else None,
            })

        return {
            "ticker": ticker,
            "points": points,
            "meta": {
                "currency": meta.get("currency", "USD"),
                "regularMarketPrice": meta.get("regularMarketPrice"),
                "previousClose": meta.get("chartPreviousClose") or meta.get("previousClose"),
                "exchangeName": meta.get("exchangeName", ""),
                "shortName": meta.get("shortName", ticker),
            },
        }
    except Exception:
        logger.exception("Yahoo chart fetch failed for %s", ticker)
        return {"ticker": ticker, "points": [], "meta": {}}
