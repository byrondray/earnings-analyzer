import json
import logging
import re
from datetime import date, datetime, timedelta
from html import escape
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import EarningsEvent, ReportTime
from app.routers.news import get_stock_news
from app.services.analysis import get_cached_analysis
from app.services.earnings_calendar import (
    fetch_recent_fallback_events,
    get_week_earnings,
    search_ticker,
    week_bounds,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["public-pages"])

_TICKER_LIMIT = 250
_TICKER_PATTERN = re.compile(r"^[A-Z]{1,5}([.\-][A-Z]{1,2})?$")
_PUBLIC_NEWS_DAYS = 14
_PUBLIC_NEWS_LIMIT = 5
_FEATURED_LIMIT = 6
_HISTORY_LIMIT = 8
_RELATED_LIMIT = 6
_STRUCTURED_DATA_EVENT_LIMIT = 20
_NEWS_DESCRIPTION_MAX_LENGTH = 300
_PAGE_CACHE_HEADER = {"Cache-Control": "public, max-age=300, stale-while-revalidate=600"}


def _absolute_url(request: Request, path: str):
    base = str(request.base_url).rstrip("/")
    clean_path = path if path.startswith("/") else f"/{path}"
    return f"{base}{clean_path}"


def _format_date(value: date | None):
    if value is None:
        return "Not available"
    return value.strftime("%A, %B %d, %Y")


def _format_short_date(value: date | None):
    if value is None:
        return "N/A"
    return value.strftime("%b %d, %Y")


def _format_currency(value: float | None, prefix: str = "$"):
    if value is None:
        return "N/A"
    sign = "-" if value < 0 else ""
    absolute = abs(value)
    if absolute >= 1_000_000_000:
        return f"{sign}{prefix}{absolute / 1_000_000_000:.2f}B"
    if absolute >= 1_000_000:
        return f"{sign}{prefix}{absolute / 1_000_000:.2f}M"
    if absolute >= 1_000:
        return f"{sign}{prefix}{absolute:,.0f}"
    return f"{sign}{prefix}{absolute:.2f}"


def _format_percent(value: float | None):
    if value is None:
        return "N/A"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def _report_time_label(value: ReportTime | str | None):
    if value == ReportTime.PRE_MARKET or value == "pre_market":
        return "Pre-market"
    if value == ReportTime.POST_MARKET or value == "post_market":
        return "After-hours"
    return "Time not specified"


def _iso_datetime(value: date | None, report_time: ReportTime | str | None = None):
    if value is None:
        return None
    hour = 21
    if report_time == ReportTime.PRE_MARKET or report_time == "pre_market":
        hour = 13
    return datetime.combine(value, datetime.min.time()).replace(hour=hour).isoformat()


def _parse_iso_datetime(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _json_ld_scripts(items: list[dict] | None):
    if not items:
        return ""
    return "\n".join(
        f'<script type="application/ld+json">{json.dumps(item, ensure_ascii=False).replace("</", "<\\/")}</script>'
        for item in items
    )



def _build_news_item(article: dict):
    url = article.get("url")
    if not url:
        return ""
    title = escape(article.get("title") or "Untitled article")
    source = escape(article.get("source") or "Unknown source")
    published = escape(article.get("publishedAt") or "Recent")
    raw_description = (article.get("description") or "")[:_NEWS_DESCRIPTION_MAX_LENGTH]
    if len(article.get("description") or "") > _NEWS_DESCRIPTION_MAX_LENGTH:
        raw_description += "…"
    description = escape(raw_description)
    description_block = f'<p class="muted" style="margin-top:8px;">{description}</p>' if description else ""
    return f"""
      <a class="mini-link" href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">
      <strong>{title}</strong><br />
      <span class="muted">{source} · {published}</span>
      {description_block}
      </a>
    """


async def _fetch_public_news_articles(ticker: str):
    response = await get_stock_news(ticker=ticker, days=_PUBLIC_NEWS_DAYS)
    payload = json.loads(response.body.decode("utf-8"))
    articles = payload.get("articles") or []
    return articles[:_PUBLIC_NEWS_LIMIT]


def _stock_news_structured_data(*, canonical_url: str, company_name: str, articles: list[dict]):
    result = []
    for article in articles:
        url = article.get("url")
        title = article.get("title")
        if not url or not title:
            continue
        result.append(
            {
                "@context": "https://schema.org",
                "@type": "NewsArticle",
                "headline": title,
                "url": url,
                "description": article.get("description") or f"Recent market coverage for {company_name} earnings.",
                "mainEntityOfPage": canonical_url,
                "publisher": {
                    "@type": "Organization",
                    "name": article.get("source") or "Earnings Analyzer",
                },
                "datePublished": article.get("publishedAt"),
            }
        )
    return result

def _breadcrumb_structured_data(request: Request, items: list[tuple[str, str]]):
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": index,
                "name": name,
                "item": _absolute_url(request, path),
            }
            for index, (name, path) in enumerate(items, start=1)
        ],
    }


def _base_structured_data(request: Request, *, title: str, description: str, canonical_url: str, page_type: str):
    website_url = _absolute_url(request, "/")
    return [
        {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": "Earnings Analyzer",
            "url": website_url,
            "description": "Track earnings calendar dates and review AI-powered stock earnings analysis.",
        },
        {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": "Earnings Analyzer",
            "url": website_url,
        },
        {
            "@context": "https://schema.org",
            "@type": page_type,
            "name": title,
            "url": canonical_url,
            "description": description,
            "isPartOf": {
                "@type": "WebSite",
                "name": "Earnings Analyzer",
                "url": website_url,
            },
        },
    ]


def _calendar_structured_data(request: Request, *, title: str, description: str, canonical_url: str, monday: date, friday: date, events: list[EarningsEvent]):
    item_list = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": title,
        "description": description,
        "url": canonical_url,
        "numberOfItems": len(events),
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": index,
                "url": _absolute_url(request, f"/stocks/{quote(event.ticker.upper())}"),
                "name": f"{event.company_name} ({event.ticker.upper()}) earnings",
            }
            for index, event in enumerate(events, start=1)
        ],
    }
    event_entries = [
        {
            "@context": "https://schema.org",
            "@type": "Event",
            "name": f"{event.company_name} ({event.ticker.upper()}) earnings report",
            "startDate": _iso_datetime(event.report_date, event.report_time),
            "eventStatus": "https://schema.org/EventScheduled" if event.report_date >= date.today() else "https://schema.org/EventCompleted",
            "eventAttendanceMode": "https://schema.org/OnlineEventAttendanceMode",
            "url": _absolute_url(request, f"/stocks/{quote(event.ticker.upper())}"),
            "organizer": {
                "@type": "Organization",
                "name": event.company_name,
            },
            "description": f"Earnings date for {event.company_name} ({event.ticker.upper()}) during the week of {monday.isoformat()} to {friday.isoformat()}.",
        }
        for event in events[:_STRUCTURED_DATA_EVENT_LIMIT]
    ]
    return [item_list, *event_entries]


def _stock_structured_data(request: Request, *, title: str, description: str, canonical_url: str, company_name: str, ticker: str, primary_event: EarningsEvent, analysis: dict | None):
    result = [
        {
            "@context": "https://schema.org",
            "@type": "Event",
            "name": f"{company_name} ({ticker}) earnings report",
            "startDate": _iso_datetime(primary_event.report_date, primary_event.report_time),
            "eventStatus": "https://schema.org/EventScheduled" if primary_event.report_date >= date.today() else "https://schema.org/EventCompleted",
            "eventAttendanceMode": "https://schema.org/OnlineEventAttendanceMode",
            "url": canonical_url,
            "organizer": {
                "@type": "Organization",
                "name": company_name,
            },
            "description": description,
        }
    ]
    if analysis:
        result.append(
            {
                "@context": "https://schema.org",
                "@type": "Article",
                "headline": title,
                "description": description,
                "mainEntityOfPage": canonical_url,
                "author": {
                    "@type": "Organization",
                    "name": "Earnings Analyzer",
                },
                "publisher": {
                    "@type": "Organization",
                    "name": "Earnings Analyzer",
                },
                "dateModified": analysis.get("analyzed_at"),
                "about": [
                    company_name,
                    f"{ticker} earnings",
                    analysis.get("sentiment") or "earnings analysis",
                ],
            }
        )
    return result


def _build_page(*, title: str, description: str, canonical_url: str, body: str, og_type: str = "website", structured_data: list[dict] | None = None, image_url: str | None = None):
    escaped_title = escape(title)
    escaped_description = escape(description)
    escaped_canonical = escape(canonical_url, quote=True)
    og_image = escape(image_url or "", quote=True)
    json_ld = _json_ld_scripts(structured_data)
    html = f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"UTF-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
    <title>{escaped_title}</title>
    <meta name=\"description\" content=\"{escaped_description}\" />
    <meta name=\"robots\" content=\"index,follow\" />
    <link rel=\"canonical\" href=\"{escaped_canonical}\" />
    <meta property=\"og:type\" content=\"{escape(og_type, quote=True)}\" />
    <meta property=\"og:title\" content=\"{escaped_title}\" />
    <meta property=\"og:description\" content=\"{escaped_description}\" />
    <meta property=\"og:url\" content=\"{escaped_canonical}\" />
    <meta property=\"og:site_name\" content=\"Earnings Analyzer\" />
    <meta property=\"og:image\" content=\"{og_image}\" />
    <meta property=\"og:locale\" content=\"en_US\" />
    <meta name=\"twitter:card\" content=\"summary_large_image\" />
    <meta name=\"twitter:title\" content=\"{escaped_title}\" />
    <meta name=\"twitter:description\" content=\"{escaped_description}\" />
    <meta name=\"twitter:url\" content=\"{escaped_canonical}\" />
    <meta name=\"twitter:image\" content=\"{og_image}\" />
    {json_ld}
    <style>
      :root {{
        color-scheme: dark;
        --bg: #0c0c0c;
        --panel: #151515;
        --text: #f5f5f5;
        --muted: #a3a3a3;
        --border: rgba(255,255,255,0.08);
        --accent: #34ac56;
        --accent-soft: rgba(52, 172, 86, 0.12);
        --gold: #d4a017;
      }}
      * {{ box-sizing: border-box; }}
      body {{ margin: 0; font-family: Inter, system-ui, sans-serif; background: radial-gradient(circle at top, rgba(52,172,86,0.16), transparent 32%), var(--bg); color: var(--text); line-height: 1.6; }}
      a {{ color: inherit; }}
      .shell {{ max-width: 1120px; margin: 0 auto; padding: 32px 24px 64px; }}
      .topbar {{ display: flex; flex-wrap: wrap; justify-content: space-between; gap: 16px; align-items: center; margin-bottom: 32px; }}
      .brand {{ font-weight: 800; font-size: 1.1rem; text-decoration: none; }}
      .brand span {{ color: var(--accent); }}
      .nav {{ display: flex; gap: 12px; flex-wrap: wrap; }}
      .nav a {{ text-decoration: none; color: var(--muted); font-size: 0.95rem; }}
      .hero {{ margin-bottom: 28px; }}
      .eyebrow {{ display: inline-flex; align-items: center; gap: 8px; padding: 6px 12px; border-radius: 999px; background: var(--accent-soft); color: var(--accent); font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; }}
      h1 {{ font-size: clamp(2rem, 4vw, 3rem); line-height: 1.1; margin: 18px 0 12px; }}
      h2 {{ font-size: 1.4rem; margin: 0 0 14px; }}
      h3 {{ font-size: 1rem; margin: 0 0 8px; }}
      p {{ margin: 0 0 12px; color: var(--muted); }}
      .grid {{ display: grid; gap: 20px; }}
      .cards {{ grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }}
      .card {{ background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01)); border: 1px solid var(--border); border-radius: 20px; padding: 20px; }}
      .metric {{ font-size: 1.55rem; font-weight: 800; color: var(--text); margin-bottom: 4px; }}
      .muted {{ color: var(--muted); }}
      .pill {{ display: inline-flex; align-items: center; gap: 8px; padding: 6px 10px; border-radius: 999px; background: rgba(255,255,255,0.05); font-size: 0.8rem; color: var(--muted); }}
      .pill strong {{ color: var(--text); }}
      .list {{ display: grid; gap: 14px; }}
      .event {{ display: flex; justify-content: space-between; gap: 18px; align-items: flex-start; text-decoration: none; background: var(--panel); border: 1px solid var(--border); border-radius: 18px; padding: 18px; }}
      .event:hover {{ border-color: rgba(52,172,86,0.45); transform: translateY(-1px); }}
      .event-meta {{ text-align: right; min-width: 170px; }}
      .event-title {{ font-size: 1.05rem; font-weight: 800; color: var(--text); margin-bottom: 2px; }}
      .ticker {{ color: var(--accent); font-weight: 800; }}
      .section {{ margin-top: 26px; }}
      .section-header {{ display: flex; justify-content: space-between; gap: 12px; align-items: baseline; margin-bottom: 14px; }}
      .section-header a {{ color: var(--accent); text-decoration: none; font-weight: 600; }}
      .breadcrumbs {{ display: flex; flex-wrap: wrap; gap: 8px; color: var(--muted); font-size: 0.92rem; margin-bottom: 16px; }}
      .breadcrumbs a {{ color: var(--muted); text-decoration: none; }}
      .summary {{ font-size: 1.02rem; max-width: 860px; }}
      .table {{ width: 100%; border-collapse: collapse; }}
      .table th, .table td {{ padding: 10px 0; border-bottom: 1px solid var(--border); text-align: left; }}
      .table td:last-child {{ color: var(--text); font-weight: 700; }}
      .split {{ display: grid; gap: 20px; grid-template-columns: 2fr 1fr; }}
      .mini-list {{ display: grid; gap: 10px; }}
      .mini-link {{ display: block; text-decoration: none; color: inherit; padding: 12px 14px; border: 1px solid var(--border); border-radius: 14px; background: rgba(255,255,255,0.02); }}
      .mini-link:hover {{ border-color: rgba(52,172,86,0.45); }}
      .footer {{ margin-top: 36px; color: var(--muted); font-size: 0.92rem; }}
      @media (max-width: 860px) {{ .split {{ grid-template-columns: 1fr; }} .event {{ flex-direction: column; }} .event-meta {{ text-align: left; min-width: 0; }} }}
    </style>
  </head>
  <body>
    <main class=\"shell\">{body}</main>
  </body>
</html>"""
    return HTMLResponse(html, headers=_PAGE_CACHE_HEADER)


def _page_shell(*, request: Request, title: str, description: str, canonical_path: str, body: str, og_type: str = "website", page_type: str = "WebPage", structured_data: list[dict] | None = None):
    canonical_url = _absolute_url(request, canonical_path)
    image_url = _absolute_url(request, "/favicon.svg")
    page_structured_data = [
        *_base_structured_data(request, title=title, description=description, canonical_url=canonical_url, page_type=page_type),
        *(structured_data or []),
    ]
    return _build_page(
        title=title,
        description=description,
        canonical_url=canonical_url,
        body=body,
        og_type=og_type,
        structured_data=page_structured_data,
        image_url=image_url,
    )


def _site_header():
    return """
      <header class=\"topbar\">
        <a class=\"brand\" href=\"/\"><span>Earnings</span> Analyzer</a>
        <nav class=\"nav\" aria-label=\"Primary\">
          <a href=\"/calendar\">Weekly earnings calendar</a>
          <a href=\"/app\">Main app</a>
        </nav>
      </header>
    """


def _build_calendar_event(event: EarningsEvent):
    stock_href = f"/stocks/{quote(event.ticker.upper())}"
    report_date = _format_date(event.report_date)
    market_cap = _format_currency(event.market_cap)
    eps_estimate = _format_currency(event.eps_estimate)
    revenue_estimate = _format_currency(event.revenue_estimate)
    return f"""
      <a class=\"event\" href=\"{stock_href}\">
        <div>
          <div class=\"event-title\"><span class=\"ticker\">{escape(event.ticker.upper())}</span> · {escape(event.company_name)}</div>
          <p>{report_date}</p>
          <p>Expected report window: {_report_time_label(event.report_time)}. Explore this stock's earnings summary, estimates, and recent report history.</p>
        </div>
        <div class=\"event-meta\">
          <div class=\"pill\"><strong>Quarter</strong> {escape(event.fiscal_quarter or 'N/A')}</div>
          <p>EPS estimate: {eps_estimate}</p>
          <p>Revenue estimate: {revenue_estimate}</p>
          <p>Market cap: {market_cap}</p>
        </div>
      </a>
    """


def _build_stock_history_item(event: EarningsEvent):
    calendar_href = f"/calendar/{event.report_date.isoformat()}"
    return f"""
      <tr>
        <td><a href=\"{calendar_href}\" style=\"color:inherit;text-decoration:none;\">{_format_short_date(event.report_date)}</a></td>
        <td>{escape(event.fiscal_quarter or 'N/A')}</td>
        <td>{escape(_report_time_label(event.report_time))}</td>
        <td>{_format_currency(event.eps_estimate)}</td>
        <td>{_format_currency(event.revenue_estimate)}</td>
      </tr>
    """


def _build_related_stock_item(event: EarningsEvent):
    href = f"/stocks/{quote(event.ticker.upper())}"
    return f"""
      <a class=\"mini-link\" href=\"{href}\">
        <strong class=\"ticker\">{escape(event.ticker.upper())}</strong> · {escape(event.company_name)}<br />
        <span class=\"muted\">{_format_short_date(event.report_date)} · {_report_time_label(event.report_time)} · Market cap { _format_currency(event.market_cap) }</span>
      </a>
    """


def _build_analysis_cards(analysis: dict | None):
    if not analysis:
        return """
          <div class=\"card\">
            <h2>Analysis snapshot</h2>
            <p>No cached AI earnings analysis is available for this stock yet. Check back after the company reports or open the app to generate a fresh analysis.</p>
          </div>
        """

    guidance = escape(analysis.get("guidance_summary") or "No guidance summary is available yet.")
    sentiment = escape((analysis.get("sentiment") or "neutral").upper())
    highlights = escape((analysis.get("raw_analysis") or {}).get("financial_highlights") or "")
    highlights_block = f'<div class="card"><h2>Financial highlights</h2><p>{highlights}</p></div>' if highlights else ""
    return f"""
      <div class=\"grid cards\">
        <section class=\"card\">
          <h2>AI earnings summary</h2>
          <p>{guidance}</p>
        </section>
        <section class=\"card\">
          <h2>Sentiment and reaction</h2>
          <div class=\"metric\">{sentiment}</div>
          <p>Sentiment score: {_format_percent((analysis.get('sentiment_score') or 0) * 100 if analysis.get('sentiment_score') is not None else None)}</p>
          <p>Post-earnings price reaction: {_format_percent(analysis.get('price_reaction_pct'))}</p>
        </section>
        <section class=\"card\">
          <h2>EPS</h2>
          <p>Estimate: {_format_currency(analysis.get('eps_estimate'))}</p>
          <p>Actual: {_format_currency(analysis.get('eps_actual'))}</p>
          <p>Surprise: {_format_percent(analysis.get('eps_surprise_pct'))}</p>
        </section>
        <section class=\"card\">
          <h2>Revenue</h2>
          <p>Estimate: {_format_currency(analysis.get('revenue_estimate'))}</p>
          <p>Actual: {_format_currency(analysis.get('revenue_actual'))}</p>
          <p>Surprise: {_format_percent(analysis.get('revenue_surprise_pct'))}</p>
        </section>
      </div>
      {highlights_block}
    """


def _build_featured_card(event: EarningsEvent):
    href = f"/stocks/{quote(event.ticker.upper())}"
    market_cap = _format_currency(event.market_cap)
    return f"""
      <a class=\"mini-link\" href=\"{href}\">
        <strong class=\"ticker\">{escape(event.ticker.upper())}</strong> · {escape(event.company_name)}<br />
        <span class=\"muted\">{_format_short_date(event.report_date)} · {_report_time_label(event.report_time)} · Market cap {market_cap}</span>
      </a>
    """


def _top_by_market_cap(events: list[EarningsEvent], limit: int):
    return sorted(events, key=lambda e: -(e.market_cap or 0))[:limit]


def _build_stock_description(company_name: str, ticker: str, primary_event: EarningsEvent | None, analysis: dict | None):
    if primary_event is None:
        return f"Review {company_name} ({ticker}) earnings analysis, historical report dates, and quarterly expectations."
    event_context = f"Next or latest earnings date: {_format_short_date(primary_event.report_date)}"
    if analysis and analysis.get("sentiment"):
        return f"Review {company_name} ({ticker}) earnings analysis, EPS and revenue context, and sentiment. {event_context}."
    return f"Track {company_name} ({ticker}) earnings date, quarterly estimates, and recent earnings history. {event_context}."


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def marketing_home(request: Request, db: AsyncSession = Depends(get_db)):
    today = date.today()
    current_monday, current_friday = week_bounds(today)
    previous_monday, previous_friday = week_bounds(today - timedelta(weeks=1))

    current_events = await get_week_earnings(db, current_monday)
    previous_events = await get_week_earnings(db, previous_monday)

    if not previous_events:
        previous_events, previous_monday, _ = await fetch_recent_fallback_events(db, current_monday)

    current_top = _top_by_market_cap(current_events, _FEATURED_LIMIT)
    previous_top = _top_by_market_cap(previous_events, _FEATURED_LIMIT)

    current_block = "".join(_build_featured_card(event) for event in current_top) or '<p class="muted">No current-week earnings data is available yet.</p>'
    previous_block = "".join(_build_featured_card(event) for event in previous_top) or '<p class="muted">No previous-week earnings data is available yet.</p>'

    title = "Earnings Analyzer | Weekly Earnings Calendar and AI Stock Earnings Analysis"
    description = "Track the weekly earnings calendar, review recent stock earnings reports, and explore AI-powered earnings analysis for public companies."

    body = f"""
      {_site_header()}
      <section class=\"hero\">
        <span class=\"eyebrow\">Public earnings hub</span>
        <h1>Weekly earnings calendar and AI-powered stock earnings analysis</h1>
        <p class=\"summary\">Follow upcoming earnings dates, revisit last week's biggest reports, and drill into company-specific earnings pages built for organic discovery and fast research.</p>
        <div class=\"nav\">
          <a href=\"/calendar\">Browse the earnings calendar</a>
          <a href=\"/app\">Open the full app</a>
        </div>
      </section>
      <section class=\"grid cards\">
        <article class=\"card\">
          <h2>Track the market-moving reports</h2>
          <p>Browse a public earnings calendar with direct links to stock-specific pages for upcoming and recently reported companies.</p>
        </article>
        <article class=\"card\">
          <h2>Review AI earnings summaries</h2>
          <p>Public stock pages surface cached earnings analysis, estimates, historical report context, and structured data for search engines.</p>
        </article>
        <article class=\"card\">
          <h2>Use the full app when you need more</h2>
          <p>Open the app for favorites, watchlists, and on-demand earnings analysis generation after you find a company worth tracking.</p>
        </article>
      </section>
      <section class=\"section\">
        <div class=\"section-header\">
          <h2>This week's top earnings</h2>
          <a href=\"/calendar/{current_monday.isoformat()}\">View full week</a>
        </div>
        <div class=\"mini-list\">{current_block}</div>
      </section>
      <section class=\"section\">
        <div class=\"section-header\">
          <h2>Last week's notable earnings</h2>
          <a href=\"/calendar/{previous_monday.isoformat()}\">Review last week</a>
        </div>
        <div class=\"mini-list\">{previous_block}</div>
      </section>
      <section class=\"section\">
        <div class=\"section-header\">
          <h2>Frequently asked questions</h2>
        </div>
        <div class=\"grid cards\">
          <article class=\"card\">
            <h3>What is an earnings calendar?</h3>
            <p>An earnings calendar shows when public companies are expected to report quarterly results, helping traders and investors plan around high-volatility dates.</p>
          </article>
          <article class=\"card\">
            <h3>What does the analysis include?</h3>
            <p>Stock pages summarize EPS and revenue expectations, post-report surprises when available, sentiment, guidance, and recent earnings history.</p>
          </article>
          <article class=\"card\">
            <h3>When should I use the app?</h3>
            <p>Use the full app when you want favorites, a personal watchlist, or on-demand analysis generation for a company after finding it through the public pages.</p>
          </article>
        </div>
      </section>
      <p class=\"footer\">Looking for the interactive experience? Head to the <a href=\"/app\">full app</a>.</p>
    """

    structured_data = [
        _breadcrumb_structured_data(request, [("Home", "/")]),
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": "What is an earnings calendar?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "An earnings calendar shows when public companies are expected to report quarterly results, helping traders and investors plan around high-volatility dates.",
                    },
                },
                {
                    "@type": "Question",
                    "name": "What does the analysis include?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "Stock pages summarize EPS and revenue expectations, post-report surprises when available, sentiment, guidance, and recent earnings history.",
                    },
                },
                {
                    "@type": "Question",
                    "name": "When should I use the app?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "Use the full app when you want favorites, a personal watchlist, or on-demand analysis generation for a company after finding it through the public pages.",
                    },
                },
            ],
        },
    ]

    return _page_shell(
        request=request,
        title=title,
        description=description,
        canonical_path="/",
        body=body,
        page_type="WebPage",
        structured_data=structured_data,
    )


@router.get("/calendar", response_class=HTMLResponse, include_in_schema=False)
async def calendar_current_week(request: Request, db: AsyncSession = Depends(get_db)):
    today = date.today()
    monday, _ = week_bounds(today)
    return await calendar_week(request, monday.isoformat(), db)


@router.get("/calendar/{week_start}", response_class=HTMLResponse, include_in_schema=False)
async def calendar_week(request: Request, week_start: str, db: AsyncSession = Depends(get_db)):
    try:
        target_date = datetime.strptime(week_start, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Invalid calendar week") from exc

    events = await get_week_earnings(db, target_date)
    monday, friday = week_bounds(target_date)
    previous_week = (monday - timedelta(weeks=1)).isoformat()
    next_week = (monday + timedelta(weeks=1)).isoformat()
    title = f"Earnings Calendar for {monday.strftime('%b %d')}–{friday.strftime('%b %d, %Y')} | Earnings Analyzer"
    description = f"Browse the earnings calendar for the week of {monday.strftime('%B %d, %Y')} and follow upcoming and recent stock earnings reports."

    grouped: dict[date, list[EarningsEvent]] = {}
    for event in events:
        grouped.setdefault(event.report_date, []).append(event)

    if grouped:
        event_sections = "".join(
            f"""
            <section class=\"section\">
              <div class=\"section-header\">
                <h2>{escape(_format_date(report_date))}</h2>
                <span class=\"pill\"><strong>{len(day_events)}</strong> reports</span>
              </div>
              <div class=\"list\">{''.join(_build_calendar_event(event) for event in day_events)}</div>
            </section>
            """
            for report_date, day_events in grouped.items()
        )
    else:
        event_sections = """
          <section class=\"card section\">
            <h2>No earnings scheduled</h2>
            <p>This week does not currently have earnings events in the database. Try the previous or next earnings calendar week.</p>
          </section>
        """

    body = f"""
      {_site_header()}
      <nav class=\"breadcrumbs\" aria-label=\"Breadcrumb\">
        <a href=\"/\">Home</a>
        <span>/</span>
        <a href=\"/calendar\">Calendar</a>
        <span>/</span>
        <span>{escape(monday.isoformat())}</span>
      </nav>
      <section class=\"hero\">
        <span class=\"eyebrow\">Weekly earnings calendar</span>
        <h1>Earnings calendar for {escape(monday.strftime('%B %d'))} – {escape(friday.strftime('%B %d, %Y'))}</h1>
        <p class=\"summary\">Browse scheduled stock earnings reports for the week, then open individual company pages to review quarterly estimates, recent report history, and cached earnings analysis.</p>
        <div class=\"nav\">
          <a href=\"/calendar/{previous_week}\">← Previous week</a>
          <a href=\"/calendar\">Current week</a>
          <a href=\"/calendar/{next_week}\">Next week →</a>
        </div>
      </section>
      {event_sections}
      <p class=\"footer\">Want a personalized watchlist and on-demand AI analysis generation? Open the <a href=\"/app\">main app</a>.</p>
    """
    canonical_path = f"/calendar/{monday.isoformat()}"
    structured_data = [
        _breadcrumb_structured_data(request, [("Home", "/"), ("Calendar", "/calendar"), (monday.isoformat(), canonical_path)]),
        *_calendar_structured_data(
            request,
            title=title,
            description=description,
            canonical_url=_absolute_url(request, canonical_path),
            monday=monday,
            friday=friday,
            events=events,
        ),
    ]
    return _page_shell(
        request=request,
        title=title,
        description=description,
        canonical_path=canonical_path,
        body=body,
        page_type="CollectionPage",
        structured_data=structured_data,
    )


@router.get("/stocks/{ticker}", response_class=HTMLResponse, include_in_schema=False)
async def stock_page(ticker: str, request: Request, db: AsyncSession = Depends(get_db)):
    upper = ticker.upper().strip()
    if not _TICKER_PATTERN.match(upper):
        raise HTTPException(status_code=404, detail="Invalid ticker")

    query = (
        select(EarningsEvent)
        .where(EarningsEvent.ticker == upper)
        .order_by(EarningsEvent.report_date.desc())
    )
    result = await db.execute(query)
    events = list(result.scalars().all())
    if not events:
        events = list(reversed(await search_ticker(db, upper)))
    if not events:
        raise HTTPException(status_code=404, detail=f"No earnings data found for {upper}")

    today = date.today()
    latest_event = max(events, key=lambda event: event.report_date)
    upcoming_event = min(
        (event for event in events if event.report_date >= today),
        key=lambda event: event.report_date,
        default=None,
    )
    primary_event = upcoming_event or latest_event
    company_name = primary_event.company_name
    try:
        analysis = await get_cached_analysis(db, upper)
    except Exception:
        logger.exception("Failed to fetch cached analysis for %s", upper)
        analysis = None
    title = f"{company_name} ({upper}) Earnings Analysis & Earnings Date | Earnings Analyzer"
    description = _build_stock_description(company_name, upper, primary_event, analysis)
    history_rows = "".join(
        _build_stock_history_item(event)
        for event in sorted(events, key=lambda event: event.report_date, reverse=True)[:_HISTORY_LIMIT]
    )
    analysis_blocks = _build_analysis_cards(analysis)
    primary_calendar_href = f"/calendar/{primary_event.report_date.isoformat()}"
    next_label = "Upcoming earnings date" if upcoming_event else "Latest earnings date"
    # Sequential, not asyncio.gather: both use the same AsyncSession (`db`),
    # and SQLAlchemy sessions aren't safe for concurrent use.
    news_articles = await _fetch_public_news_articles(upper)
    week_events = await get_week_earnings(db, primary_event.report_date)
    news_block = "".join(
      _build_news_item(article)
      for article in news_articles
      if article.get("url")
    )

    related_events = [
        event
        for event in week_events
        if event.ticker.upper() != upper
    ][:_RELATED_LIMIT]
    related_block = ""
    if related_events:
        related_block = f"""
          <section class=\"card\">
            <h2>Other companies reporting this week</h2>
            <div class=\"mini-list\">{''.join(_build_related_stock_item(event) for event in related_events)}</div>
          </section>
        """

    body = f"""
      {_site_header()}
      <nav class=\"breadcrumbs\" aria-label=\"Breadcrumb\">
        <a href=\"/\">Home</a>
        <span>/</span>
        <a href=\"/calendar\">Calendar</a>
        <span>/</span>
        <span>{escape(upper)}</span>
      </nav>
      <section class=\"hero\">
        <span class=\"eyebrow\">Stock earnings page</span>
        <h1>{escape(company_name)} <span class=\"ticker\">({escape(upper)})</span></h1>
        <p class=\"summary\">Track the next or latest earnings date for {escape(company_name)}, review consensus estimates, and see cached AI analysis for recent quarterly results.</p>
        <div class=\"nav\">
          <a href=\"{primary_calendar_href}\">View this earnings week</a>
          <a href=\"/#/stock/{quote(upper)}\">Open in the app</a>
        </div>
      </section>
          <section class="card">
            <h2>Recent earnings news</h2>
            <div class="mini-list">
              {news_block if news_block else '<p class="muted">No recent earnings news is available right now.</p>'}
            </div>
          </section>
      <section class=\"split\">
        <div class=\"grid\">
          <section class=\"card\">
            <h2>{next_label}</h2>
            <div class=\"metric\">{escape(_format_short_date(primary_event.report_date))}</div>
            <p>{escape(_report_time_label(primary_event.report_time))}</p>
            <p>Fiscal quarter: {escape(primary_event.fiscal_quarter or 'N/A')}</p>
            <p>EPS estimate: {_format_currency(primary_event.eps_estimate)}</p>
            <p>Revenue estimate: {_format_currency(primary_event.revenue_estimate)}</p>
            <p>Market cap: {_format_currency(primary_event.market_cap)}</p>
          </section>
          {analysis_blocks}
          <section class=\"card\">
            <div class=\"section-header\">
              <h2>Recent earnings history</h2>
              <a href=\"{primary_calendar_href}\">Browse the calendar week</a>
            </div>
            <table class=\"table\">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Quarter</th>
                  <th>Report window</th>
                  <th>EPS est.</th>
                  <th>Revenue est.</th>
                </tr>
              </thead>
              <tbody>
                {history_rows}
              </tbody>
            </table>
          </section>
        </div>
        <aside class=\"grid\">
          <section class=\"card\">
            <h2>Why this page exists</h2>
            <p>This public page makes earnings dates, quarterly estimates, and recent stock earnings analysis easier to discover without logging in.</p>
          </section>
          {related_block}
          <section class=\"card\">
            <h2>Explore more earnings pages</h2>
            <p><a href=\"/calendar\" style=\"color:var(--accent);text-decoration:none;\">Browse this week's earnings calendar</a></p>
            <p><a href=\"/app\" style=\"color:var(--accent);text-decoration:none;\">Launch the main app</a></p>
            <p class=\"muted\">Use the app for favorites, watchlists, and on-demand analysis generation.</p>
          </section>
        </aside>
      </section>
    """
    canonical_path = f"/stocks/{quote(upper)}"
    canonical_url = _absolute_url(request, canonical_path)
    structured_data = [
        _breadcrumb_structured_data(request, [("Home", "/"), ("Calendar", "/calendar"), (upper, canonical_path)]),
        *_stock_structured_data(
            request,
            title=title,
            description=description,
        canonical_url=canonical_url,
            company_name=company_name,
            ticker=upper,
            primary_event=primary_event,
            analysis=analysis,
        ),
      *_stock_news_structured_data(
        canonical_url=canonical_url,
        company_name=company_name,
        articles=news_articles,
      ),
    ]
    return _page_shell(
        request=request,
        title=title,
        description=description,
        canonical_path=canonical_path,
        body=body,
        og_type="article",
        page_type="Article",
        structured_data=structured_data,
    )


async def get_public_sitemap_entries(db: AsyncSession):
    today = date.today()
    current_week, _ = week_bounds(today)
    paths = [
        {"path": "/", "changefreq": "daily", "priority": "1.0", "lastmod": today.isoformat()},
        {"path": "/calendar", "changefreq": "daily", "priority": "0.9", "lastmod": today.isoformat()},
        {"path": f"/calendar/{current_week.isoformat()}", "changefreq": "daily", "priority": "0.9", "lastmod": today.isoformat()},
    ]

    for offset in (-1, 1):
        week_start = current_week + timedelta(weeks=offset)
        paths.append(
            {
                "path": f"/calendar/{week_start.isoformat()}",
                "changefreq": "daily",
                "priority": "0.7",
                "lastmod": today.isoformat(),
            }
        )

    ticker_query = (
        select(EarningsEvent.ticker, func.max(EarningsEvent.report_date))
        .where(EarningsEvent.report_date >= today - timedelta(days=30))
        .where(EarningsEvent.report_date <= today + timedelta(days=120))
        .group_by(EarningsEvent.ticker)
        .order_by(func.max(EarningsEvent.report_date).desc(), EarningsEvent.ticker)
        .limit(_TICKER_LIMIT)
    )
    ticker_result = await db.execute(ticker_query)
    tickers = list(ticker_result.all())
    for ticker, report_date in tickers:
        paths.append(
            {
                "path": f"/stocks/{quote(ticker.upper())}",
                "changefreq": "daily",
                "priority": "0.8",
                "lastmod": report_date.isoformat() if report_date else today.isoformat(),
            }
        )

    return paths