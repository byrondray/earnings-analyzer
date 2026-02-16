import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
import httpx

from app.config import get_settings
from app.services.cache import get_cached, set_cached

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("/{ticker}")
async def get_stock_news(
    ticker: str,
    days: int = Query(default=30, ge=1, le=90),
):
    upper = ticker.upper().strip()
    cache_key = f"news:{upper}:{days}"

    cached = await get_cached(cache_key)
    if cached is not None:
        return JSONResponse(cached)

    settings = get_settings()
    articles = []

    if settings.NEWS_API_KEY:
        articles = await _fetch_newsapi(upper, days, settings.NEWS_API_KEY)

    if not articles:
        articles = await _fetch_brave_news(upper, settings.BRAVE_SEARCH_API_KEY)

    result = {"ticker": upper, "articles": articles}
    await set_cached(cache_key, result, ttl=3600)
    return JSONResponse(result)


async def _fetch_newsapi(ticker: str, days: int, api_key: str) -> list[dict]:
    from_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": f"{ticker} stock earnings",
        "from": from_date,
        "sortBy": "relevancy",
        "pageSize": 15,
        "language": "en",
        "apiKey": api_key,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
        data = resp.json()
        if data.get("status") != "ok":
            logger.warning("NewsAPI error: %s", data.get("message"))
            return []

        return [
            {
                "title": a.get("title", ""),
                "description": a.get("description", ""),
                "url": a.get("url", ""),
                "source": a.get("source", {}).get("name", ""),
                "publishedAt": a.get("publishedAt", ""),
                "imageUrl": a.get("urlToImage"),
            }
            for a in data.get("articles", [])
            if a.get("title") and "[Removed]" not in a.get("title", "")
        ]
    except Exception:
        logger.exception("NewsAPI fetch failed for %s", ticker)
        return []


async def _fetch_brave_news(ticker: str, api_key: str) -> list[dict]:
    if not api_key:
        return []

    url = "https://api.search.brave.com/res/v1/news/search"
    params = {"q": f"{ticker} stock earnings", "count": 15}
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params, headers=headers)
        data = resp.json()
        results = data.get("results", [])
        return [
            {
                "title": r.get("title", ""),
                "description": r.get("description", ""),
                "url": r.get("url", ""),
                "source": r.get("meta_url", {}).get("hostname", ""),
                "publishedAt": r.get("age", ""),
                "imageUrl": r.get("thumbnail", {}).get("src"),
            }
            for r in results
        ]
    except Exception:
        logger.exception("Brave News fetch failed for %s", ticker)
        return []
