from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from app.mcp_server.tools.analyze import analyze_earnings, ANALYSIS_TOOL


class TestAnalyzeEarnings:
    @pytest.mark.asyncio
    async def test_returns_structured_result(self, sample_analysis_result):
        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "earnings_analysis_result"
        mock_tool_block.input = sample_analysis_result

        mock_response = MagicMock()
        mock_response.content = [mock_tool_block]

        mock_client = AsyncMock()
        mock_client.messages.create.return_value = mock_response

        with patch(
            "app.mcp_server.tools.analyze.anthropic.AsyncAnthropic",
            return_value=mock_client,
        ):
            result = await analyze_earnings("AAPL", "Some earnings data text")

        assert result["eps_actual"] == 2.45
        assert result["sentiment"] == "bullish"
        assert result["guidance_summary"] is not None

    @pytest.mark.asyncio
    async def test_returns_error_on_no_tool_use(self):
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "I cannot analyze this."

        mock_response = MagicMock()
        mock_response.content = [mock_text_block]

        mock_client = AsyncMock()
        mock_client.messages.create.return_value = mock_response

        with patch(
            "app.mcp_server.tools.analyze.anthropic.AsyncAnthropic",
            return_value=mock_client,
        ):
            result = await analyze_earnings("AAPL", "Some earnings data")

        assert "error" in result

    @pytest.mark.asyncio
    async def test_passes_correct_model_and_tool(self, sample_analysis_result):
        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "earnings_analysis_result"
        mock_tool_block.input = sample_analysis_result

        mock_response = MagicMock()
        mock_response.content = [mock_tool_block]

        mock_client = AsyncMock()
        mock_client.messages.create.return_value = mock_response

        with patch(
            "app.mcp_server.tools.analyze.anthropic.AsyncAnthropic",
            return_value=mock_client,
        ):
            await analyze_earnings("AAPL", "Some data")

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-20250514"
        assert call_kwargs["tools"] == [ANALYSIS_TOOL]
        assert call_kwargs["tool_choice"] == {
            "type": "tool",
            "name": "earnings_analysis_result",
        }


class TestAnalysisToolSchema:
    def test_tool_has_required_fields(self):
        schema = ANALYSIS_TOOL["input_schema"]
        required = schema["required"]
        expected = [
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
        ]
        assert set(required) == set(expected)

    def test_sentiment_enum_values(self):
        sentiment_prop = ANALYSIS_TOOL["input_schema"]["properties"]["sentiment"]
        assert sentiment_prop["enum"] == ["bullish", "bearish", "neutral"]
