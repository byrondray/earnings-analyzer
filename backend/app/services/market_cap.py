import asyncio
import logging

import httpx

from app.config import get_settings
from app.services.cache import (
    get_cached_market_cap,
    get_many_cached_market_caps,
    set_cached_market_cap,
    set_many_cached_market_caps,
)

logger = logging.getLogger(__name__)

FMP_PROFILE_URL = "https://financialmodelingprep.com/stable/profile"

_CONCURRENT_LIMIT = 10
_BATCH_SIZE = 20


async def _fetch_market_cap_from_api(
    ticker: str, client: httpx.AsyncClient | None = None
) -> float | None:
    settings = get_settings()
    params = {"symbol": ticker, "apikey": settings.FMP_API_KEY}
    should_close = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=5.0)
    try:
        resp = await client.get(FMP_PROFILE_URL, params=params)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if isinstance(data, list) and len(data) > 0:
            return data[0].get("marketCap")
    except Exception:
        return None
    finally:
        if should_close:
            await client.aclose()
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
        settings = get_settings()
        batches = [missing[i:i + _BATCH_SIZE] for i in range(0, len(missing), _BATCH_SIZE)]
        logger.info("Fetching market caps for %d tickers in %d batch(es)", len(missing), len(batches))

        async with httpx.AsyncClient(timeout=10.0) as client:
            for batch in batches:
                symbol_str = ",".join(batch)
                try:
                    resp = await client.get(
                        FMP_PROFILE_URL,
                        params={"symbol": symbol_str, "apikey": settings.FMP_API_KEY},
                    )
                    if resp.status_code != 200:
                        logger.warning("FMP batch request failed with %d", resp.status_code)
                        continue
                    data = resp.json()
                    if isinstance(data, list):
                        for profile in data:
                            t = profile.get("symbol", "").upper()
                            cap = profile.get("marketCap")
                            if t and cap is not None:
                                cached[t] = cap
                except Exception as e:
                    logger.warning("FMP batch fetch error: %s", e)

        to_cache = {t: cached[t] for t in missing if cached[t] is not None}
        if to_cache:
            await set_many_cached_market_caps(to_cache)
            logger.info("Cached market caps for %d/%d tickers", len(to_cache), len(missing))

    return cached
