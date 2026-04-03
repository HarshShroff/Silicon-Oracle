from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolContext:
    """Context passed to each tool handler - includes user info."""

    user_id: str | None = None
    session_data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    handler: Callable[[dict[str, Any], ToolContext], Any]
    required_permissions: tuple[str, ...] = ()
    is_read_only: bool = True
    category: str = "general"

    def execute(self, payload: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        try:
            result = self.handler(payload, context)
            return {
                "success": True,
                "tool": self.name,
                "result": result,
            }
        except PermissionError as e:
            return {
                "success": False,
                "tool": self.name,
                "error": f"Permission denied: {str(e)}",
                "error_type": "permission",
            }
        except Exception as e:
            return {
                "success": False,
                "tool": self.name,
                "error": str(e),
                "error_type": "execution",
            }


@dataclass(frozen=True)
class AgentCommand:
    name: str
    description: str
    handler: Callable[[str], str]

    def execute(self, prompt: str) -> str:
        try:
            return self.handler(prompt)
        except Exception as e:
            return f"Command '{self.name}' failed: {str(e)}"


@dataclass
class ExecutionRegistry:
    tools: tuple[AgentTool, ...]
    commands: tuple[AgentCommand, ...]
    _tool_index: dict[str, AgentTool] = field(default_factory=dict, init=False)
    _command_index: dict[str, AgentCommand] = field(default_factory=dict, init=False)

    def __post_init__(self):
        self._tool_index = {t.name.lower(): t for t in self.tools}
        self._command_index = {c.name.lower(): c for c in self.commands}

    def tool(self, name: str) -> AgentTool | None:
        return self._tool_index.get(name.lower())

    def command(self, name: str) -> AgentCommand | None:
        return self._command_index.get(name.lower())

    def has_tool(self, name: str) -> bool:
        return name.lower() in self._tool_index

    def has_command(self, name: str) -> bool:
        return name.lower() in self._command_index

    def filter_by_category(self, category: str) -> tuple[AgentTool, ...]:
        return tuple(t for t in self.tools if t.category == category)

    def filter_read_only(self) -> tuple[AgentTool, ...]:
        return tuple(t for t in self.tools if t.is_read_only)


def _create_stock_quote_handler() -> Callable[[dict[str, Any], ToolContext], Any]:
    def handler(payload: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        ticker = payload.get("ticker", "").upper()
        if not ticker:
            return {"error": "ticker required"}

        try:
            from flask_app.services import StockService

            stock_service = StockService()
            quote = stock_service.get_realtime_quote(ticker)
            if quote:
                return {
                    "ticker": ticker,
                    "price": quote.get("current"),
                    "change": quote.get("change_percent"),
                }
            return {"error": f"No quote found for {ticker}"}
        except Exception as e:
            return {"error": str(e)}

    return handler


def _create_portfolio_value_handler() -> Callable[[dict[str, Any], ToolContext], Any]:
    def handler(payload: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        if not context.user_id:
            return {"error": "User not authenticated"}

        try:
            from flask_app.services import PortfolioService

            portfolio_service = PortfolioService(context.user_id)
            trades = portfolio_service.get_trade_history(limit=100)

            holdings = {}
            for trade in trades:
                ticker = trade.get("ticker")
                if ticker:
                    if ticker not in holdings:
                        holdings[ticker] = {"shares": 0.0, "avg_price": 0.0}
                    side = trade.get("side", "").lower()
                    qty = float(trade.get("quantity", 0))
                    if side == "buy":
                        holdings[ticker]["shares"] += qty
                    elif side == "sell":
                        holdings[ticker]["shares"] -= qty

            return {"holdings": holdings, "trade_count": len(trades)}
        except Exception as e:
            return {"error": str(e)}

    return handler


def _create_search_ticker_handler() -> Callable[[dict[str, Any], ToolContext], Any]:
    def handler(payload: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        query = payload.get("query", "").strip()
        if not query or len(query) < 1:
            return {"results": []}

        try:
            import yfinance as yf

            results = []
            upper = query.upper().replace(" ", "-")
            if len(upper) <= 5 and upper.isalpha():
                try:
                    info = yf.Ticker(upper).fast_info
                    price = getattr(info, "last_price", None) or getattr(
                        info, "regularMarketPrice", None
                    )
                    if price:
                        results.append({"ticker": upper, "price": round(float(price), 2)})
                except Exception:
                    pass

            return {"results": results[:8]}
        except Exception as e:
            return {"error": str(e)}

    return handler


def _create_oracle_analysis_handler() -> Callable[[dict[str, Any], ToolContext], Any]:
    def handler(payload: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        ticker = payload.get("ticker", "").upper()
        if not ticker:
            return {"error": "ticker required"}

        try:
            from flask_app.services import OracleService, StockService

            stock_service = StockService()
            oracle_service = OracleService()

            quote = stock_service.get_realtime_quote(ticker)
            analysis = oracle_service.calculate_oracle_score(ticker)

            return {
                "ticker": ticker,
                "price": quote.get("current") if quote else 0,
                "score": analysis.get("confidence", 0),
                "verdict": analysis.get("verdict", "HOLD"),
                "factors": analysis.get("factors", []),
            }
        except Exception as e:
            return {"error": str(e)}

    return handler


def _create_news_fetch_handler() -> Callable[[dict[str, Any], ToolContext], Any]:
    def handler(payload: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        ticker = payload.get("ticker", "").upper()
        if not ticker:
            return {"error": "ticker required"}

        try:
            from flask_app.services import StockService

            stock_service = StockService()
            news = stock_service.get_news(ticker)
            return {"ticker": ticker, "news": news[:5] if news else []}
        except Exception as e:
            return {"error": str(e)}

    return handler


def _create_watchlist_get_handler() -> Callable[[dict[str, Any], ToolContext], Any]:
    def handler(payload: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        if not context.user_id:
            return {"error": "User not authenticated"}

        try:
            from flask_app.services.scanner_service import WATCHLISTS
            from utils import database as db

            user_watchlists_list = db.get_user_watchlists(context.user_id)
            user_watchlists_dict = {
                row.get("name", ""): row.get("tickers", []) for row in user_watchlists_list
            }
            all_watchlists = {**user_watchlists_dict, **WATCHLISTS}

            return {"watchlists": all_watchlists}
        except Exception as e:
            return {"error": str(e)}

    return handler


def build_execution_registry(
    extra_tools: tuple[AgentTool, ...] = (),
    extra_commands: tuple[AgentCommand, ...] = (),
) -> ExecutionRegistry:
    """Build execution registry with real service handlers."""
    tools: tuple[AgentTool, ...] = (
        AgentTool(
            name="stock_quote",
            description="Get real-time stock quote",
            handler=_create_stock_quote_handler(),
            required_permissions=("market_data",),
            is_read_only=True,
            category="market_data",
        ),
        AgentTool(
            name="portfolio_value",
            description="Get current portfolio value",
            handler=_create_portfolio_value_handler(),
            required_permissions=("read_portfolio",),
            is_read_only=True,
            category="portfolio",
        ),
        AgentTool(
            name="search_ticker",
            description="Search for ticker by symbol or company name",
            handler=_create_search_ticker_handler(),
            required_permissions=("market_data",),
            is_read_only=True,
            category="market_data",
        ),
        AgentTool(
            name="oracle_analysis",
            description="Get Oracle AI analysis for a ticker",
            handler=_create_oracle_analysis_handler(),
            required_permissions=("market_data", "ai_analysis"),
            is_read_only=True,
            category="ai_analysis",
        ),
        AgentTool(
            name="news_fetch",
            description="Fetch latest news for a ticker",
            handler=_create_news_fetch_handler(),
            required_permissions=("market_data",),
            is_read_only=True,
            category="news",
        ),
        AgentTool(
            name="watchlist_get",
            description="Get user's stock watchlists",
            handler=_create_watchlist_get_handler(),
            required_permissions=("read_watchlist",),
            is_read_only=True,
            category="watchlist",
        ),
    )

    commands: tuple[AgentCommand, ...] = (
        AgentCommand(
            name="scan",
            description="Scan watchlist for opportunities",
            handler=lambda p: "Scanning watchlist for opportunities...",
        ),
        AgentCommand(
            name="analyze",
            description="Analyze a stock",
            handler=lambda p: f"Analyzing {p}...",
        ),
        AgentCommand(
            name="help",
            description="Show available commands",
            handler=lambda p: (
                "Use stock_quote, portfolio_value, search_ticker, oracle_analysis, news_fetch, watchlist_get"
            ),
        ),
    )

    return ExecutionRegistry(tools=tools + extra_tools, commands=commands + extra_commands)


DEFAULT_TOOLS: tuple[AgentTool, ...] = ()
DEFAULT_COMMANDS: tuple[AgentCommand, ...] = ()
