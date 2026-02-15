import json

import anthropic

from app.config import get_settings

ANALYSIS_TOOL = {
    "name": "earnings_analysis_result",
    "description": "Return a structured earnings analysis with all extracted financial metrics.",
    "input_schema": {
        "type": "object",
        "properties": {
            "eps_estimate": {
                "type": "number",
                "description": "Consensus EPS estimate before the report",
            },
            "eps_actual": {
                "type": "number",
                "description": "Actual reported EPS",
            },
            "eps_surprise_pct": {
                "type": "number",
                "description": "EPS surprise as a percentage ((actual - estimate) / |estimate| * 100)",
            },
            "revenue_estimate": {
                "type": "number",
                "description": "Consensus revenue estimate in dollars",
            },
            "revenue_actual": {
                "type": "number",
                "description": "Actual reported revenue in dollars",
            },
            "revenue_surprise_pct": {
                "type": "number",
                "description": "Revenue surprise as a percentage",
            },
            "guidance_summary": {
                "type": "string",
                "description": "1-3 sentence summary of forward guidance provided by management",
            },
            "sentiment": {
                "type": "string",
                "enum": ["bullish", "bearish", "neutral"],
                "description": "Overall sentiment of the earnings report",
            },
            "sentiment_score": {
                "type": "number",
                "description": "Sentiment confidence score from 0.0 to 1.0",
            },
            "price_reaction_pct": {
                "type": "number",
                "description": "Stock price change percentage in after-hours or next trading day",
            },
        },
        "required": [
            "eps_estimate",
            "eps_actual",
            "eps_surprise_pct",
            "revenue_estimate",
            "revenue_actual",
            "revenue_surprise_pct",
            "guidance_summary",
            "sentiment",
            "sentiment_score",
            "price_reaction_pct",
        ],
    },
}

SYSTEM_PROMPT = """You are a financial analyst specializing in earnings report analysis.
Given search results about a company's earnings report, extract the key financial metrics
and provide your analysis. Use the earnings_analysis_result tool to return your structured analysis.

Rules:
- Extract actual numbers from the search results when available
- If a specific number isn't available, make your best estimate based on context
- Revenue values should be in raw dollars (e.g., 94.9 billion = 94900000000)
- EPS values should be in dollars per share
- Surprise percentages: ((actual - estimate) / |estimate|) * 100
- Guidance summary should be concise (1-3 sentences)
- Sentiment should reflect the overall tone: bullish, bearish, or neutral
- Sentiment score: 0.0 = no confidence, 1.0 = very confident
- Price reaction: estimated or actual after-hours/next-day price change percentage"""


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
