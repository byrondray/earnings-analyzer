import json

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

SYSTEM_PROMPT = """You are a financial analyst specializing in earnings report analysis.
Given search results about a company's earnings report, extract the key financial metrics
and provide your analysis. Use the earnings_analysis_result tool to return your structured analysis.

CRITICAL RULES:
- Today's date is important. If the earnings report has NOT been released yet (report date
  is today or in the future and no actual results are found in the search data), set
  has_reported=false and return null for: eps_actual, eps_surprise_pct, revenue_actual,
  revenue_surprise_pct, guidance_summary, and price_reaction_pct.
- NEVER fabricate or estimate actual earnings numbers. Only use numbers explicitly stated
  in the search results.
- You may still provide eps_estimate, revenue_estimate, sentiment (based on market
  expectations), and sentiment_score for upcoming reports.

Formatting rules:
- Revenue values should be in raw dollars (e.g., 94.9 billion = 94900000000)
- EPS values should be in dollars per share
- Surprise percentages: ((actual - estimate) / |estimate|) * 100
- Guidance summary should be concise (1-3 sentences)
- Sentiment should reflect the overall tone: bullish, bearish, or neutral
- Sentiment score: 0.0 = no confidence, 1.0 = very confident
- Price reaction: actual after-hours/next-day price change percentage"""


async def analyze_earnings(ticker: str, earnings_data: str) -> dict:
    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        tools=[ANALYSIS_TOOL],
        tool_choice={"type": "tool", "name": "earnings_analysis_result"},
        messages=[
            {
                "role": "user",
                "content": f"Analyze the following earnings report data for {ticker}:\n\n{earnings_data}",
            }
        ],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "earnings_analysis_result":
            return block.input

    return {"error": "Claude did not return a tool use response"}
