from datetime import date, datetime, timedelta
from html import escape
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import EarningsEvent, ReportTime
from app.services.analysis import get_cached_analysis
from app.services.earnings_calendar import get_week_earnings, search_ticker, week_bounds

router = APIRouter(tags=["public-pages"])

_TICKER_LIMIT = 250


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
    absolute = abs(value)
    if absolute >= 1_000_000_000:
        return f"{prefix}{value / 1_000_000_000:.2f}B"
    if absolute >= 1_000_000:
        return f"{prefix}{value / 1_000_000:.2f}M"
    if absolute >= 1_000:
        return f"{prefix}{value:,.0f}"
    return f"{prefix}{value:.2f}"


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


def _build_page(*, title: str, description: str, canonical_url: str, body: str, og_type: str = "website"):
    escaped_title = escape(title)
    escaped_description = escape(description)
    escaped_canonical = escape(canonical_url, quote=True)
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
    <meta name=\"twitter:card\" content=\"summary_large_image\" />
    <meta name=\"twitter:title\" content=\"{escaped_title}\" />
    <meta name=\"twitter:description\" content=\"{escaped_description}\" />
    <style>
      :root {{
        color-scheme: dark;
        --bg: #0c0c0c;
        --panel: #151515;
        --panel-alt: #1d1d1d;
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
      .copy a {{ color: var(--accent); text-decoration: none; }}
      .summary {{ font-size: 1.02rem; max-width: 860px; }}
      .table {{ width: 100%; border-collapse: collapse; }}
      .table td {{ padding: 10px 0; border-bottom: 1px solid var(--border); }}
      .table td:last-child {{ text-align: right; color: var(--text); font-weight: 700; }}
      .split {{ display: grid; gap: 20px; grid-template-columns: 2fr 1fr; }}
      .tag {{ display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 0.78rem; background: rgba(212,160,23,0.12); color: var(--gold); font-weight: 700; }}
      .footer {{ margin-top: 36px; color: var(--muted); font-size: 0.92rem; }}
      @media (max-width: 860px) {{ .split {{ grid-template-columns: 1fr; }} .event {{ flex-direction: column; }} .event-meta {{ text-align: left; min-width: 0; }} }}
    </style>
  </head>
  <body>
    <main class=\"shell\">{body}</main>
  </body>
</html>"""
    return HTMLResponse(html)


def _page_shell(*, request: Request, title: str, description: str, canonical_path: str, body: str):
    canonical_url = _absolute_url(request, canonical_path)
    return _build_page(title=title, description=description, canonical_url=canonical_url, body=body)


def _site_header():
    return """
      <header class=\"topbar\">
        <a class=\"brand\" href=\"/\"><span>Earnings</span> Analyzer</a>
        <nav class=\"nav\" aria-label=\"Primary\">
          <a href=\"/calendar\">Weekly earnings calendar</a>
          <a href=\"/\">Main app</a>
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
          <p class=\"copy\">Expected report window: {_report_time_label(event.report_time)}. Explore this stock's earnings summary, estimates, and recent report history.</p>
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
    highlights_block = f"<div class=\"card\"><h2>Financial highlights</h2><p>{highlights}</p></div>" if highlights else ""
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


def _build_stock_description(company_name: str, ticker: str, primary_event: EarningsEvent | None, analysis: dict | None):
    if primary_event is None:
        return f"Review {company_name} ({ticker}) earnings analysis, historical report dates, and quarterly expectations."
    event_context = f"Next or latest earnings date: {_format_short_date(primary_event.report_date)}"
    if analysis and analysis.get("sentiment"):
        return f"Review {company_name} ({ticker}) earnings analysis, EPS and revenue context, and sentiment. {event_context}."
    return f"Track {company_name} ({ticker}) earnings date, quarterly estimates, and recent earnings history. {event_context}."


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
      <p class=\"footer\">Want a personalized watchlist and on-demand AI analysis generation? Open the <a href=\"/\">main app</a>.</p>
    """
    return _page_shell(request=request, title=title, description=description, canonical_path=f"/calendar/{monday.isoformat()}", body=body)


@router.get("/stocks/{ticker}", response_class=HTMLResponse, include_in_schema=False)
async def stock_page(ticker: str, request: Request, db: AsyncSession = Depends(get_db)):
    upper = ticker.upper().strip()
    if not upper.isalpha() or len(upper) > 10:
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
    analysis = await get_cached_analysis(db, upper)
    title = f"{company_name} ({upper}) Earnings Analysis & Earnings Date | Earnings Analyzer"
    description = _build_stock_description(company_name, upper, primary_event, analysis)
    history_rows = "".join(_build_stock_history_item(event) for event in sorted(events, key=lambda event: event.report_date, reverse=True)[:8])
    analysis_blocks = _build_analysis_cards(analysis)
    primary_calendar_href = f"/calendar/{primary_event.report_date.isoformat()}"
    next_label = "Upcoming earnings date" if upcoming_event else "Latest earnings date"

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
            <table class=\"table\" aria-label=\"Recent earnings history\">
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
          <section class=\"card\">
            <h2>Explore more earnings pages</h2>
            <p><a href=\"/calendar\" style=\"color:var(--accent);text-decoration:none;\">Browse this week's earnings calendar</a></p>
            <p><a href=\"/\" style=\"color:var(--accent);text-decoration:none;\">Launch the main app</a></p>
            <p class=\"muted\">Use the app for favorites, watchlists, and on-demand analysis generation.</p>
          </section>
        </aside>
      </section>
    """
    return _page_shell(request=request, title=title, description=description, canonical_path=f"/stocks/{quote(upper)}", body=body)


async def get_public_sitemap_entries(db: AsyncSession):
    today = date.today()
    current_week, _ = week_bounds(today)
    paths = [
        {"path": "/", "changefreq": "daily", "priority": "1.0"},
        {"path": "/calendar", "changefreq": "daily", "priority": "0.9"},
        {"path": f"/calendar/{current_week.isoformat()}", "changefreq": "daily", "priority": "0.9"},
    ]

    for offset in (-1, 1):
        week_start = (current_week + timedelta(weeks=offset)).isoformat()
        paths.append({"path": f"/calendar/{week_start}", "changefreq": "daily", "priority": "0.7"})

    ticker_query = (
        select(EarningsEvent.ticker)
        .where(EarningsEvent.report_date >= today - timedelta(days=30))
        .where(EarningsEvent.report_date <= today + timedelta(days=120))
        .distinct()
        .order_by(EarningsEvent.ticker)
        .limit(_TICKER_LIMIT)
    )
    ticker_result = await db.execute(ticker_query)
    tickers = list(ticker_result.scalars().all())
    for ticker in tickers:
        paths.append({"path": f"/stocks/{quote(ticker.upper())}", "changefreq": "daily", "priority": "0.8"})

    return paths