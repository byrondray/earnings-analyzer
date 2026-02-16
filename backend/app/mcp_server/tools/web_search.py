import asyncio
import logging
import re

import httpx
from bs4 import BeautifulSoup

from app.config import get_settings

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"

logger = logging.getLogger(__name__)

_MAX_PAGES = 3
_PAGE_TIMEOUT = 8.0
_MAX_CHARS_PER_PAGE = 4000
_TOTAL_CHAR_LIMIT = 12000


def _extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]):
        tag.decompose()

    article = soup.find("article") or soup.find("main") or soup.find("body")
    if not article:
        return ""

    text = article.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:_MAX_CHARS_PER_PAGE]


async def _fetch_page(client: httpx.AsyncClient, url: str) -> str:
    try:
        resp = await client.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            follow_redirects=True,
            timeout=_PAGE_TIMEOUT,
        )
        if resp.status_code != 200:
            return ""
        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type:
            return ""
        return _extract_text(resp.text)
    except Exception:
        return ""


async def search_earnings_report(ticker: str, quarter: str, company_name: str | None = None) -> str:
    settings = get_settings()
    name_part = f'"{company_name}"' if company_name and company_name != ticker else ticker
    query = f"{name_part} {ticker} {quarter} earnings report results revenue EPS guidance outlook stock price reaction"

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            BRAVE_SEARCH_URL,
            params={"q": query, "count": 5},
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": settings.BRAVE_SEARCH_API_KEY,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    results = data.get("web", {}).get("results", [])
    if not results:
        return f"No search results found for {ticker} {quarter} earnings."

    lines = [f"Search results for {ticker} {quarter} earnings:\n"]
    for i, r in enumerate(results[:5], 1):
        lines.append(f"{i}. {r.get('title', 'No title')}")
        lines.append(f"   URL: {r.get('url', '')}")
        lines.append(f"   {r.get('description', 'No description')}")
        lines.append("")

    urls = [r.get("url", "") for r in results[:_MAX_PAGES] if r.get("url")]
    async with httpx.AsyncClient() as client:
        pages = await asyncio.gather(*[_fetch_page(client, url) for url in urls])

    total_chars = 0
    for i, (url, text) in enumerate(zip(urls, pages)):
        if not text:
            continue
        remaining = _TOTAL_CHAR_LIMIT - total_chars
        if remaining <= 0:
            break
        trimmed = text[:remaining]
        lines.append(f"--- Article {i+1} content ({url}) ---")
        lines.append(trimmed)
        lines.append("")
        total_chars += len(trimmed)
        logger.info("Fetched %d chars from %s", len(trimmed), url)

    return "\n".join(lines)
