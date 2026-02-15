import httpx

from app.config import get_settings

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


async def search_earnings_report(ticker: str, quarter: str) -> str:
    settings = get_settings()
    query = f"{ticker} {quarter} earnings report results revenue EPS"

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

    return "\n".join(lines)
