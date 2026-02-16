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
_MAX_CHARS_PER_PAGE = 6000
_TOTAL_CHAR_LIMIT = 20000

_PRIMARY_SOURCE_DOMAINS = [
    "businesswire.com",
    "prnewswire.com",
    "globenewswire.com",
    "sec.gov",
    "investor",
    "ir.",
    "investors.",
]


def _is_primary_source(url: str) -> bool:
    lower = url.lower()
    return any(domain in lower for domain in _PRIMARY_SOURCE_DOMAINS)


def _extract_text(html: str, max_chars: int = _MAX_CHARS_PER_PAGE) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]):
        tag.decompose()

    article = soup.find("article") or soup.find("main") or soup.find("body")
    if not article:
        return ""

    text = article.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:max_chars]


async def _fetch_page(client: httpx.AsyncClient, url: str, max_chars: int = _MAX_CHARS_PER_PAGE) -> str:
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
        return _extract_text(resp.text, max_chars)
    except Exception:
        return ""


async def _search_brave(client: httpx.AsyncClient, query: str, api_key: str, count: int = 5) -> list[dict]:
    resp = await client.get(
        BRAVE_SEARCH_URL,
        params={"q": query, "count": count},
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": api_key,
        },
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("web", {}).get("results", [])


async def search_earnings_report(ticker: str, quarter: str, company_name: str | None = None) -> str:
    settings = get_settings()
    name_part = f'"{company_name}"' if company_name and company_name != ticker else ticker

    press_release_query = f"{name_part} {ticker} {quarter} earnings press release results"
    reaction_query = f"{ticker} {quarter} earnings stock price reaction after-hours"

    async with httpx.AsyncClient(timeout=15.0) as client:
        press_results, reaction_results = await asyncio.gather(
            _search_brave(client, press_release_query, settings.BRAVE_SEARCH_API_KEY, count=5),
            _search_brave(client, reaction_query, settings.BRAVE_SEARCH_API_KEY, count=3),
        )

    all_results = press_results + reaction_results
    if not all_results:
        return f"No search results found for {ticker} {quarter} earnings."

    seen_urls = set()
    primary_urls = []
    secondary_urls = []

    for r in all_results:
        url = r.get("url", "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        if _is_primary_source(url):
            primary_urls.append(r)
        else:
            secondary_urls.append(r)

    lines = [f"Search results for {ticker} {quarter} earnings:\n"]
    for i, r in enumerate(all_results[:8], 1):
        source_tag = " [PRESS RELEASE]" if _is_primary_source(r.get("url", "")) else ""
        lines.append(f"{i}. {r.get('title', 'No title')}{source_tag}")
        lines.append(f"   URL: {r.get('url', '')}")
        lines.append(f"   {r.get('description', 'No description')}")
        lines.append("")

    # Prioritize press releases, then fill with news articles
    fetch_order = primary_urls[:3] + secondary_urls[:3]
    fetch_order = fetch_order[:5]
    urls = [r.get("url", "") for r in fetch_order if r.get("url")]

    async with httpx.AsyncClient() as client:
        # Give press releases more chars
        tasks = []
        for r in fetch_order:
            url = r.get("url", "")
            if not url:
                continue
            chars = 8000 if _is_primary_source(url) else _MAX_CHARS_PER_PAGE
            tasks.append(_fetch_page(client, url, chars))
        pages = await asyncio.gather(*tasks)

    total_chars = 0
    for i, (r, text) in enumerate(zip(fetch_order, pages)):
        if not text:
            continue
        url = r.get("url", "")
        remaining = _TOTAL_CHAR_LIMIT - total_chars
        if remaining <= 0:
            break
        trimmed = text[:remaining]
        source_label = "PRESS RELEASE" if _is_primary_source(url) else "Article"
        lines.append(f"--- {source_label} {i+1} content ({url}) ---")
        lines.append(trimmed)
        lines.append("")
        total_chars += len(trimmed)
        logger.info("Fetched %d chars from %s (%s)", len(trimmed), url, source_label)

    return "\n".join(lines)
