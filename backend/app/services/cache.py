import json
from typing import Any

import redis.asyncio as redis

from app.config import get_settings

_redis_client: redis.Redis | None = None

EARNINGS_CALENDAR_TTL = 4 * 60 * 60  # 4 hours
AV_SYNC_TTL = 4 * 60 * 60  # 4 hours - throttle Alpha Vantage bulk syncs
MARKET_CAP_TTL = 24 * 60 * 60  # 24 hours
ANALYSIS_TTL = 7 * 24 * 60 * 60  # 7 days
ANALYSIS_UNREPORTED_TTL = 4 * 60 * 60  # 4 hours for pre-report analyses
HIGHLIGHTS_TTL = 4 * 60 * 60  # 4 hours
SPARKLINE_TTL = 12 * 60 * 60  # 12 hours


async def get_redis() -> redis.Redis | None:
    global _redis_client
    settings = get_settings()
    if not settings.REDIS_URL:
        return None
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _redis_client


async def close_redis():
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


def _calendar_key(week_start: str) -> str:
    return f"earnings:calendar:{week_start}"


def _market_cap_key(ticker: str) -> str:
    return f"earnings:mcap:{ticker.upper()}"


async def get_cached_calendar(week_start: str) -> list[dict] | None:
    return await get_cached(_calendar_key(week_start))


async def set_cached_calendar(week_start: str, events: list[dict]):
    await set_cached(_calendar_key(week_start), events, ttl=EARNINGS_CALENDAR_TTL)


async def get_cached_market_cap(ticker: str) -> float | None:
    r = await get_redis()
    if r is None:
        return None
    try:
        data = await r.get(_market_cap_key(ticker))
        if data:
            return float(data)
    except Exception:
        pass
    return None


async def set_cached_market_cap(ticker: str, market_cap: float):
    r = await get_redis()
    if r is None:
        return
    try:
        await r.setex(
            _market_cap_key(ticker),
            MARKET_CAP_TTL,
            str(market_cap),
        )
    except Exception:
        pass


async def get_many_cached_market_caps(tickers: list[str]) -> dict[str, float | None]:
    r = await get_redis()
    if r is None:
        return {t: None for t in tickers}
    try:
        keys = [_market_cap_key(t) for t in tickers]
        values = await r.mget(keys)
        result = {}
        for ticker, val in zip(tickers, values):
            result[ticker] = float(val) if val else None
        return result
    except Exception:
        return {t: None for t in tickers}


async def set_many_cached_market_caps(caps: dict[str, float]):
    r = await get_redis()
    if r is None:
        return
    try:
        pipe = r.pipeline()
        for ticker, cap in caps.items():
            pipe.setex(_market_cap_key(ticker), MARKET_CAP_TTL, str(cap))
        await pipe.execute()
    except Exception:
        pass


def _analysis_key(ticker: str, quarter: str) -> str:
    return f"earnings:analysis:{ticker.upper()}:{quarter}"


async def get_cached_analysis_redis(ticker: str, quarter: str) -> dict | None:
    r = await get_redis()
    if r is None:
        return None
    try:
        data = await r.get(_analysis_key(ticker, quarter))
        if data:
            return json.loads(data)
    except Exception:
        pass
    return None


async def set_cached_analysis_redis(ticker: str, quarter: str, analysis: dict):
    r = await get_redis()
    if r is None:
        return
    try:
        ttl = ANALYSIS_TTL if analysis.get("has_reported") is True else ANALYSIS_UNREPORTED_TTL
        await r.setex(
            _analysis_key(ticker, quarter),
            ttl,
            json.dumps(analysis, default=str),
        )
    except Exception:
        pass


_HIGHLIGHTS_KEY = "earnings:highlights:v4"


async def get_cached_highlights() -> dict | None:
    r = await get_redis()
    if r is None:
        return None
    try:
        data = await r.get(_HIGHLIGHTS_KEY)
        if data:
            return json.loads(data)
    except Exception:
        pass
    return None


async def set_cached_highlights(highlights: dict):
    r = await get_redis()
    if r is None:
        return
    try:
        await r.setex(
            _HIGHLIGHTS_KEY,
            HIGHLIGHTS_TTL,
            json.dumps(highlights, default=str),
        )
    except Exception:
        pass


def _sparkline_key(ticker: str) -> str:
    return f"earnings:sparkline:{ticker.upper()}"


async def get_cached_sparkline(ticker: str) -> list[float] | None:
    r = await get_redis()
    if r is None:
        return None
    try:
        data = await r.get(_sparkline_key(ticker))
        if data:
            return json.loads(data)
    except Exception:
        pass
    return None


async def set_cached_sparkline(ticker: str, prices: list[float], ttl: int = SPARKLINE_TTL):
    r = await get_redis()
    if r is None:
        return
    try:
        await r.setex(
            _sparkline_key(ticker),
            ttl,
            json.dumps(prices),
        )
    except Exception:
        pass


async def get_cached(key: str) -> Any | None:
    r = await get_redis()
    if r is None:
        return None
    try:
        data = await r.get(key)
        if data:
            return json.loads(data)
    except Exception:
        pass
    return None


async def set_cached(key: str, value: Any, ttl: int = 3600):
    r = await get_redis()
    if r is None:
        return
    try:
        await r.setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        pass


def _analysis_lock_key(ticker: str, quarter: str) -> str:
    return f"earnings:analysis_lock:{ticker.upper()}:{quarter}"


ANALYSIS_LOCK_TTL = 90  # seconds; generous upper bound for search + Claude call


async def acquire_analysis_lock(ticker: str, quarter: str) -> bool:
    """Best-effort lock so concurrent requests for the same ticker/quarter
    don't each pay for a separate Brave + Claude run. Returns True if the
    caller acquired the lock (should proceed), False if another request is
    already running it. No-ops (returns True) when Redis is unavailable."""
    r = await get_redis()
    if r is None:
        return True
    try:
        return bool(await r.set(_analysis_lock_key(ticker, quarter), "1", nx=True, ex=ANALYSIS_LOCK_TTL))
    except Exception:
        return True


async def release_analysis_lock(ticker: str, quarter: str):
    r = await get_redis()
    if r is None:
        return
    try:
        await r.delete(_analysis_lock_key(ticker, quarter))
    except Exception:
        pass


_AV_SYNC_KEY = "earnings:av_last_sync"


async def should_sync_alpha_vantage() -> bool:
    r = await get_redis()
    if r is None:
        return True
    try:
        return await r.get(_AV_SYNC_KEY) is None
    except Exception:
        return True


async def mark_alpha_vantage_synced(ttl: int | None = None):
    r = await get_redis()
    if r is None:
        return
    try:
        await r.setex(_AV_SYNC_KEY, ttl or AV_SYNC_TTL, "1")
    except Exception:
        pass


AV_TICKER_SEARCH_TTL = 4 * 60 * 60  # 4 hours; throttles per-ticker AV lookups triggered by search


def _av_ticker_search_key(ticker: str) -> str:
    return f"earnings:av_ticker_search:{ticker.upper()}"


async def should_search_alpha_vantage(ticker: str) -> bool:
    r = await get_redis()
    if r is None:
        return True
    try:
        return await r.get(_av_ticker_search_key(ticker)) is None
    except Exception:
        return True


async def mark_alpha_vantage_searched(ticker: str):
    r = await get_redis()
    if r is None:
        return
    try:
        await r.setex(_av_ticker_search_key(ticker), AV_TICKER_SEARCH_TTL, "1")
    except Exception:
        pass
