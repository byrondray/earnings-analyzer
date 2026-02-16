import json
from datetime import date

import anthropic

from app.config import get_settings

ANALYSIS_TOOL = {
    "name": "earnings_analysis_result",
    "description": "Return a structured earnings analysis with all extracted financial metrics.",
    "input_schema": {
        "type": "object",
        "properties": {
            "has_reported": {
                "type": "boolean",
                "description": "Whether the company has already reported earnings. False if the report date is in the future.",
            },
            "eps_estimate": {
                "type": ["number", "null"],
                "description": "Consensus EPS estimate before the report",
            },
            "eps_actual": {
                "type": ["number", "null"],
                "description": "Actual reported EPS. Must be null if has_reported is false.",
            },
            "eps_surprise_pct": {
                "type": ["number", "null"],
                "description": "EPS surprise as a percentage ((actual - estimate) / |estimate| * 100). Must be null if has_reported is false.",
            },
            "revenue_estimate": {
                "type": ["number", "null"],
                "description": "Consensus revenue estimate in dollars",
            },
            "revenue_actual": {
                "type": ["number", "null"],
                "description": "Actual reported revenue in dollars. Must be null if has_reported is false.",
            },
            "revenue_surprise_pct": {
                "type": ["number", "null"],
                "description": "Revenue surprise as a percentage. Must be null if has_reported is false.",
            },
            "guidance_summary": {
                "type": ["string", "null"],
                "description": "1-3 sentence summary of forward guidance provided by management. Null if not yet reported.",
            },
            "financial_highlights": {
                "type": ["string", "null"],
                "description": "Key financial metrics from the earnings report: operating income, net income, gross/operating margins, free cash flow, segment breakdowns, YoY comparisons. Use bullet points. Null if not yet reported.",
            },
            "sentiment": {
                "type": "string",
                "enum": ["bullish", "bearish", "neutral"],
                "description": "Overall sentiment — pre-report expectations if not yet reported, post-report analysis if reported",
            },
            "sentiment_score": {
                "type": "number",
                "description": "Sentiment confidence score from 0.0 to 1.0",
            },
            "price_reaction_pct": {
                "type": ["number", "null"],
                "description": "Stock price change percentage in after-hours or next trading day. Must be null if has_reported is false.",
            },
        },
        "required": [
            "has_reported",
            "eps_estimate",
            "revenue_estimate",
            "sentiment",
            "sentiment_score",
        ],
    },
}

SYSTEM_PROMPT = """You are a senior financial accountant and analyst reviewing a company's quarterly earnings.
You have been given the actual earnings press release and related coverage. Your job is to
extract precise financial metrics directly from the primary source data and provide a
thorough accounting-focused analysis.

Use the earnings_analysis_result tool to return your structured analysis.

CRITICAL RULES:
- Today's date is important. If the earnings report has NOT been released yet (report date
  is today or in the future and no actual results are found), set has_reported=false and
  return null for all actual/post-report fields.
- NEVER fabricate numbers. Only use figures explicitly stated in the source material.
- Prioritize data from PRESS RELEASE sources over news articles — press releases contain
  the official numbers from the company.
- If the search results contain insufficient data to extract financial metrics, you MUST
  still provide helpful context in guidance_summary and financial_highlights. Explain what
  data was or wasn't available, summarize whatever you did find, and note the company's
  reporting status. Do NOT leave both guidance_summary and financial_highlights null/empty
  when search results exist — always give the user something useful.

FINANCIAL DATA EXTRACTION (accountant perspective):
- EPS: Look for "earnings per share", "diluted EPS", "adjusted EPS", "net income per share".
  Use diluted/adjusted EPS if both GAAP and non-GAAP are available, note the distinction.
- Revenue: "revenue", "net revenue", "total revenue", "net sales". Convert to raw dollars.
  "$95.4 billion" = 95400000000, "$4.2 million" = 4200000.
- Operating Income: "operating income", "income from operations", "EBIT".
- Net Income: "net income", "net earnings", "bottom line".
- Margins: Gross margin, operating margin — calculate from data if not stated.
- Free Cash Flow: "free cash flow", "FCF", "cash from operations minus capex".
- Segment Revenue: Break down by business segment if available.
- YoY Growth: Compare to year-ago quarter if mentioned.

For financial_highlights, provide a bullet-point breakdown of:
• Operating income and margin
• Net income
• Free cash flow
• Segment performance (if available)
• Notable YoY changes
• Any non-GAAP adjustments or one-time items

PRICE REACTION:
- Look for "shares rose/fell X%", "stock up/down X%", "after-hours trading",
  "pre-market", "next trading day". Extract the actual percentage.

GUIDANCE:
- Look for "outlook", "expects", "guidance", "forecast", "projects", "raised/lowered".
- Summarize management's forward-looking statements about next quarter or full year.

SURPRISE CALCULATION:
- If you have both estimate and actual: ((actual - estimate) / |estimate|) * 100

Formatting rules:
- Revenue/income values in raw dollars (94.9 billion = 94900000000)
- EPS in dollars per share
- Percentages as numbers (3.2 not "3.2%")
- Guidance summary: concise 1-3 sentences
- Financial highlights: bullet points with actual numbers"""


def _build_event_context(ticker: str, event_context: dict | None) -> str:
    if not event_context:
        return ""
    parts = [f"\nKnown data for {ticker} from our database:"]
    if event_context.get("company_name"):
        parts.append(f"- Company: {event_context['company_name']}")
    if event_context.get("report_date"):
        parts.append(f"- Report date: {event_context['report_date']}")
    if event_context.get("eps_estimate") is not None:
        parts.append(f"- EPS estimate: ${event_context['eps_estimate']}")
    if event_context.get("revenue_estimate") is not None:
        parts.append(f"- Revenue estimate: ${event_context['revenue_estimate']:,.0f}")
    if event_context.get("fiscal_quarter"):
        parts.append(f"- Fiscal quarter ending: {event_context['fiscal_quarter']}")
    return "\n".join(parts)


async def analyze_earnings(ticker: str, earnings_data: str, event_context: dict | None = None) -> dict:
    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    context_str = _build_event_context(ticker, event_context)
    company_hint = ""
    if event_context and event_context.get("company_name"):
        company_hint = f" ({event_context['company_name']})"

    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=f"{SYSTEM_PROMPT}\n\nToday's date: {date.today().isoformat()}",
        tools=[ANALYSIS_TOOL],
        tool_choice={"type": "tool", "name": "earnings_analysis_result"},
        messages=[
            {
                "role": "user",
                "content": f"Analyze the following earnings report data for {ticker}{company_hint}:\n{context_str}\n\n{earnings_data}",
            }
        ],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "earnings_analysis_result":
            return block.input

    return {"error": "Claude did not return a tool use response"}
