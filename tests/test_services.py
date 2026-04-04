"""
Tests for Silicon Oracle services.
Run with: pytest tests/test_services.py -v
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ---------------------------------------------------------------------------
# StockService
# ---------------------------------------------------------------------------


class TestStockService:
    """Tests for StockService."""

    def test_init_without_config(self):
        """StockService initializes without config."""
        from flask_app.services.stock_service import StockService

        svc = StockService()
        assert svc is not None
        assert svc.config == {}

    def test_init_with_config(self):
        """StockService stores provided config."""
        from flask_app.services.stock_service import StockService

        svc = StockService({"FINNHUB_API_KEY": "test"})
        assert svc.config.get("FINNHUB_API_KEY") == "test"

    def test_get_company_info_returns_dict(self):
        """get_company_info always returns a dict even without API."""
        from flask_app.services.stock_service import StockService

        svc = StockService()
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.info = {}
            result = svc.get_company_info("AAPL")
        assert isinstance(result, dict)
        assert result["ticker"] == "AAPL"

    def test_get_news_returns_list(self):
        """get_news returns a list (may be empty)."""
        from flask_app.services.stock_service import StockService

        svc = StockService()
        with patch("feedparser.parse") as mock_parse:
            mock_parse.return_value = MagicMock(entries=[])
            result = svc.get_news("AAPL")
        assert isinstance(result, list)

    def test_get_market_status_returns_dict(self):
        """get_market_status always returns a dict."""
        from flask_app.services.stock_service import StockService

        svc = StockService()
        result = svc.get_market_status()
        assert isinstance(result, dict)
        assert "is_open" in result
        assert "session" in result

    def test_get_market_status_session_values(self):
        """get_market_status session field is a known value."""
        from flask_app.services.stock_service import StockService

        svc = StockService()
        result = svc.get_market_status()
        assert result["session"] in ("pre-market", "regular", "after-hours", "closed")


# ---------------------------------------------------------------------------
# OracleService
# ---------------------------------------------------------------------------


class TestOracleService:
    """Tests for OracleService."""

    def test_init(self):
        """OracleService initializes."""
        from flask_app.services.oracle_service import OracleService

        svc = OracleService()
        assert svc is not None

    def test_calculate_oracle_score_returns_dict(self):
        """calculate_oracle_score returns a dict with required keys."""
        from flask_app.services.oracle_service import OracleService

        svc = OracleService()
        mock_data = {
            "quote": {"current": 150.0, "percent_change": 1.0},
            "company": {"pe_ratio": 25, "beta": 1.1, "target_price": 180},
            "technicals": None,
            "earnings": None,
            "recommendations": None,
            "price_targets": None,
            "insiders": None,
        }
        with patch.object(svc.stock_service, "get_complete_data", return_value=mock_data):
            result = svc.calculate_oracle_score("AAPL")
        assert isinstance(result, dict)
        assert "verdict" in result or "error" in result


# ---------------------------------------------------------------------------
# EmailService
# ---------------------------------------------------------------------------


class TestEmailService:
    """Tests for EmailService."""

    def test_init_unconfigured(self):
        """EmailService reports not configured without credentials."""
        from flask_app.services.email_service import EmailService

        svc = EmailService()
        assert svc.is_configured() is False
        assert svc.enabled is False

    def test_init_configured(self):
        """EmailService reports configured with credentials."""
        from flask_app.services.email_service import EmailService

        svc = EmailService({"gmail_address": "test@gmail.com", "gmail_app_password": "pass"})
        assert svc.is_configured() is True

    def test_send_email_unconfigured_returns_false(self):
        """send_email returns False when not configured."""
        from flask_app.services.email_service import EmailService

        svc = EmailService()
        result = svc.send_email("to@example.com", "Subject", "<p>Body</p>")
        assert result is False


# ---------------------------------------------------------------------------
# AgentRuntime
# ---------------------------------------------------------------------------


class TestAgentRuntime:
    """Tests for AgentRuntime."""

    def test_build_runtime(self):
        """build_agent_runtime returns an AgentRuntime."""
        from flask_app.agent.runtime import build_agent_runtime

        runtime = build_agent_runtime(user_id="test-user")
        assert runtime is not None
        assert runtime.user_id == "test-user"

    def test_get_available_tools(self):
        """get_available_tools returns a tuple of tools."""
        from flask_app.agent.runtime import build_agent_runtime

        runtime = build_agent_runtime()
        tools = runtime.get_available_tools()
        assert isinstance(tools, tuple)
        assert len(tools) > 0

    def test_route_prompt_returns_matches(self):
        """route_prompt scores tools against prompt tokens."""
        from flask_app.agent.runtime import build_agent_runtime

        runtime = build_agent_runtime()
        matches = runtime.route_prompt("get stock quote for AAPL")
        assert isinstance(matches, list)

    def test_permission_blocks_tool(self):
        """ToolPermissionContext blocks denied tools."""
        from flask_app.agent.permissions import ToolPermissionContext

        ctx = ToolPermissionContext.from_iterables(deny_names=["stock_quote"])
        assert ctx.blocks("stock_quote") is True
        assert ctx.blocks("portfolio_value") is False

    def test_permission_prefix_blocking(self):
        """ToolPermissionContext blocks by prefix."""
        from flask_app.agent.permissions import ToolPermissionContext

        ctx = ToolPermissionContext.from_iterables(deny_prefixes=["stock_"])
        assert ctx.blocks("stock_quote") is True
        assert ctx.blocks("portfolio_value") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
