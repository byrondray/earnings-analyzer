from mcp.server.fastmcp import FastMCP

from app.mcp_server.tools.web_search import search_earnings_report
from app.mcp_server.tools.analyze import analyze_earnings

mcp_server = FastMCP("earnings-analyzer")


@mcp_server.tool()
async def search_earnings(ticker: str, quarter: str) -> str:
    """Search the web for a company's earnings report for a given quarter.

    Args:
        ticker: Stock ticker symbol (e.g., AAPL, MSFT)
        quarter: Fiscal quarter (e.g., Q4-2025, Q1-2026)
    """
    return await search_earnings_report(ticker, quarter)


@mcp_server.tool()
async def analyze_earnings_report(ticker: str, earnings_data: str) -> dict:
    """Analyze earnings report data using Claude to extract key financial metrics.

    Args:
        ticker: Stock ticker symbol
        earnings_data: Raw text of earnings report data from web search
    """
    return await analyze_earnings(ticker, earnings_data)
