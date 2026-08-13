import json
import logging
from typing import Any

import redis.asyncio as redis

from app.config import get_settings

logger = logging.getLogger(__name__)

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


async def get_cached(key: str) -> Any | None:
    r = await get_redis()
    if r is None:
        return None
    try:
        data = await r.get(key)
        if data:
            return json.loads(data)
    except Exception:
        logger.warning("Redis get failed for key %s", key, exc_info=True)
    return None


async def set_cached(key: str, value: Any, ttl: int = 3600):
    r = await get_redis()
    if r is None:
        return
    try:
        await r.setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        logger.warning("Redis set failed for key %s", key, exc_info=True)


def _calendar_key(week_start: str) -> str:
    return f"earnings:calendar:{week_start}"


def _market_cap_key(ticker: str) -> str:
    return f"earnings:mcap:{ticker.upper()}"


async def get_cached_calendar(week_start: str) -> list[dict] | None:
    return await get_cached(_calendar_key(week_start))


async def set_cached_calendar(week_start: str, events: list[dict]):
    await set_cached(_calendar_key(week_start), events, ttl=EARNINGS_CALENDAR_TTL)


async def get_cached_market_cap(ticker: str) -> float | None:
    value = await get_cached(_market_cap_key(ticker))
    return float(value) if value is not None else None


async def set_cached_market_cap(ticker: str, market_cap: float):
    await set_cached(_market_cap_key(ticker), market_cap, ttl=MARKET_CAP_TTL)


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
        logger.warning("Redis mget failed for %d tickers", len(tickers), exc_info=True)
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
        logger.warning("Redis pipeline set failed for %d tickers", len(caps), exc_info=True)


def _analysis_key(ticker: str, quarter: str) -> str:
    return f"earnings:analysis:{ticker.upper()}:{quarter}"


async def get_cached_analysis_redis(ticker: str, quarter: str) -> dict | None:
    return await get_cached(_analysis_key(ticker, quarter))


async def set_cached_analysis_redis(ticker: str, quarter: str, analysis: dict):
    ttl = ANALYSIS_TTL if analysis.get("has_reported") is True else ANALYSIS_UNREPORTED_TTL
    await set_cached(_analysis_key(ticker, quarter), analysis, ttl=ttl)


_HIGHLIGHTS_KEY = "earnings:highlights:v4"


async def get_cached_highlights() -> dict | None:
    return await get_cached(_HIGHLIGHTS_KEY)


async def set_cached_highlights(highlights: dict):
    await set_cached(_HIGHLIGHTS_KEY, highlights, ttl=HIGHLIGHTS_TTL)


def _sparkline_key(ticker: str) -> str:
    return f"earnings:sparkline:{ticker.upper()}"


async def get_cached_sparkline(ticker: str) -> list[float] | None:
    return await get_cached(_sparkline_key(ticker))


async def set_cached_sparkline(ticker: str, prices: list[float], ttl: int = SPARKLINE_TTL):
    await set_cached(_sparkline_key(ticker), prices, ttl=ttl)


def _analysis_lock_key(ticker: str, quarter: str) -> str:
    return f"earnings:analysis_lock:{ticker.upper()}:{quarter}"


ANALYSIS_LOCK_TTL = 90  # seconds; generous upper bound for search + Claude call


_local_locks: set[str] = set()


async def _acquire_lock(key: str, ttl: int) -> bool:
    """Best-effort lock so concurrent requests for the same key don't each
    pay for a separate round of external API calls. Returns True if the
    caller acquired the lock (should proceed), False if another request is
    already running it.

    Normally backed by Redis (works across processes/instances). When Redis
    is unavailable, falls back to an in-process lock set so a Redis outage
    at least prevents duplicate paid API calls within a single instance,
    rather than silently disabling the lock entirely."""
    r = await get_redis()
    if r is None:
        return _acquire_local_lock(key)
    try:
        return bool(await r.set(key, "1", nx=True, ex=ttl))
    except Exception:
        logger.warning("Redis lock acquisition failed, falling back to in-process lock for %s", key)
        return _acquire_local_lock(key)


async def _release_lock(key: str):
    _local_locks.discard(key)
    r = await get_redis()
    if r is None:
        return
    try:
        await r.delete(key)
    except Exception:
        logger.warning("Redis lock release failed for %s", key)


def _acquire_local_lock(key: str) -> bool:
    if key in _local_locks:
        return False
    _local_locks.add(key)
    return True


async def acquire_analysis_lock(ticker: str, quarter: str) -> bool:
    return await _acquire_lock(_analysis_lock_key(ticker, quarter), ANALYSIS_LOCK_TTL)


async def release_analysis_lock(ticker: str, quarter: str):
    await _release_lock(_analysis_lock_key(ticker, quarter))


def _ticker_search_lock_key(ticker: str) -> str:
    return f"earnings:ticker_search_lock:{ticker.upper()}"


TICKER_SEARCH_LOCK_TTL = 40  # seconds; comfortably covers sequential Nasdaq (15s) + FMP (15s) timeouts


async def acquire_ticker_search_lock(ticker: str) -> bool:
    return await _acquire_lock(_ticker_search_lock_key(ticker), TICKER_SEARCH_LOCK_TTL)


async def release_ticker_search_lock(ticker: str):
    await _release_lock(_ticker_search_lock_key(ticker))


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
