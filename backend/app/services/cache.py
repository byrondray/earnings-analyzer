import json
from typing import Any

import redis.asyncio as redis

from app.config import get_settings

_redis_client: redis.Redis | None = None

EARNINGS_CALENDAR_TTL = 4 * 60 * 60  # 4 hours
MARKET_CAP_TTL = 24 * 60 * 60  # 24 hours


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
    r = await get_redis()
    if r is None:
        return None
    try:
        data = await r.get(_calendar_key(week_start))
        if data:
            return json.loads(data)
    except Exception:
        pass
    return None


async def set_cached_calendar(week_start: str, events: list[dict]):
    r = await get_redis()
    if r is None:
        return
    try:
        await r.setex(
            _calendar_key(week_start),
            EARNINGS_CALENDAR_TTL,
            json.dumps(events),
        )
    except Exception:
        pass


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
