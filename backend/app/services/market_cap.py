import asyncio

import httpx

from app.config import get_settings
from app.services.cache import (
    get_cached_market_cap,
    get_many_cached_market_caps,
    set_cached_market_cap,
    set_many_cached_market_caps,
)

FMP_PROFILE_URL = "https://financialmodelingprep.com/stable/profile"

# Concurrency limit to avoid hammering the API
_CONCURRENT_LIMIT = 5


async def _fetch_market_cap_from_api(ticker: str) -> float | None:
    settings = get_settings()
    params = {"symbol": ticker, "apikey": settings.FMP_API_KEY}
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(FMP_PROFILE_URL, params=params)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if isinstance(data, list) and len(data) > 0:
            return data[0].get("marketCap")
    return None


async def fetch_market_cap(ticker: str) -> float | None:
    cached = await get_cached_market_cap(ticker)
    if cached is not None:
        return cached

    market_cap = await _fetch_market_cap_from_api(ticker)
    if market_cap is not None:
        await set_cached_market_cap(ticker, market_cap)
    return market_cap


async def fetch_market_caps_batch(tickers: list[str]) -> dict[str, float | None]:
    if not tickers:
        return {}

    unique_tickers = list(set(tickers))
    cached = await get_many_cached_market_caps(unique_tickers)

    missing = [t for t in unique_tickers if cached[t] is None]

    if missing:
        semaphore = asyncio.Semaphore(_CONCURRENT_LIMIT)

        async def _limited_fetch(t: str) -> tuple[str, float | None]:
            async with semaphore:
                val = await _fetch_market_cap_from_api(t)
                return (t, val)

        results = await asyncio.gather(*[_limited_fetch(t) for t in missing])

        to_cache = {}
        for ticker, cap in results:
            if cap is not None:
                cached[ticker] = cap
                to_cache[ticker] = cap

        if to_cache:
            await set_many_cached_market_caps(to_cache)

    return cached
