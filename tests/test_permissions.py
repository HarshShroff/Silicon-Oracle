"""
Tests for flask_app/agent/permissions.py
"""


from flask_app.agent.execution_registry import AgentTool
from flask_app.agent.permissions import (
    ToolPermissionContext,
    create_secure_permission_context,
)


def make_tool(name: str) -> AgentTool:
    return AgentTool(
        name=name,
        description=f"Tool: {name}",
        handler=lambda payload, ctx: {},
        is_read_only=True,
        category="test",
    )


class TestBlocks:
    def test_empty_context_blocks_nothing(self):
        ctx = ToolPermissionContext()
        assert ctx.blocks("stock_quote") is False
        assert ctx.blocks("any_tool") is False

    def test_blocks_by_exact_name(self):
        ctx = ToolPermissionContext.from_iterables(deny_names=["stock_quote"])
        assert ctx.blocks("stock_quote") is True
        assert ctx.blocks("portfolio_value") is False

    def test_blocks_case_insensitive(self):
        ctx = ToolPermissionContext.from_iterables(deny_names=["Stock_Quote"])
        assert ctx.blocks("stock_quote") is True
        assert ctx.blocks("STOCK_QUOTE") is True
        assert ctx.blocks("Stock_Quote") is True

    def test_blocks_by_prefix(self):
        ctx = ToolPermissionContext.from_iterables(deny_prefixes=["stock_"])
        assert ctx.blocks("stock_quote") is True
        assert ctx.blocks("stock_price") is True
        assert ctx.blocks("portfolio_value") is False

    def test_prefix_case_insensitive(self):
        ctx = ToolPermissionContext.from_iterables(deny_prefixes=["STOCK_"])
        assert ctx.blocks("stock_quote") is True
        assert ctx.blocks("STOCK_QUOTE") is True

    def test_multiple_names_blocked(self):
        ctx = ToolPermissionContext.from_iterables(deny_names=["tool_a", "tool_b", "tool_c"])
        assert ctx.blocks("tool_a") is True
        assert ctx.blocks("tool_b") is True
        assert ctx.blocks("tool_c") is True
        assert ctx.blocks("tool_d") is False

    def test_multiple_prefixes_blocked(self):
        ctx = ToolPermissionContext.from_iterables(deny_prefixes=["db_", "sql_"])
        assert ctx.blocks("db_query") is True
        assert ctx.blocks("sql_execute") is True
        assert ctx.blocks("redis_get") is False

    def test_exact_name_does_not_match_prefix(self):
        """Exact deny_name 'stock' should not block 'stock_quote'."""
        ctx = ToolPermissionContext.from_iterables(deny_names=["stock"])
        assert ctx.blocks("stock") is True
        assert ctx.blocks("stock_quote") is False  # different tool

    def test_none_inputs(self):
        ctx = ToolPermissionContext.from_iterables(deny_names=None, deny_prefixes=None)
        assert ctx.blocks("anything") is False


class TestFilterTools:
    def test_returns_all_when_no_denials(self):
        ctx = ToolPermissionContext()
        tools = (make_tool("tool_a"), make_tool("tool_b"))
        result = ctx.filter_tools(tools)
        assert len(result) == 2

    def test_removes_blocked_tools(self):
        ctx = ToolPermissionContext.from_iterables(deny_names=["tool_a"])
        tools = (make_tool("tool_a"), make_tool("tool_b"), make_tool("tool_c"))
        result = ctx.filter_tools(tools)
        names = [t.name for t in result]
        assert "tool_a" not in names
        assert "tool_b" in names
        assert "tool_c" in names

    def test_removes_prefix_blocked_tools(self):
        ctx = ToolPermissionContext.from_iterables(deny_prefixes=["db_"])
        tools = (make_tool("db_read"), make_tool("db_write"), make_tool("cache_get"))
        result = ctx.filter_tools(tools)
        names = [t.name for t in result]
        assert "db_read" not in names
        assert "db_write" not in names
        assert "cache_get" in names

    def test_empty_tools_tuple(self):
        ctx = ToolPermissionContext.from_iterables(deny_names=["x"])
        assert ctx.filter_tools(()) == ()


class TestGetDenials:
    def test_no_denials_empty(self):
        ctx = ToolPermissionContext()
        tools = (make_tool("stock_quote"),)
        assert ctx.get_denials(tools) == ()

    def test_denial_has_correct_tool_name(self):
        ctx = ToolPermissionContext.from_iterables(deny_names=["stock_quote"])
        tools = (make_tool("stock_quote"),)
        denials = ctx.get_denials(tools)
        assert len(denials) == 1
        assert denials[0].tool_name == "stock_quote"

    def test_denial_has_reason(self):
        ctx = ToolPermissionContext.from_iterables(deny_names=["stock_quote"])
        tools = (make_tool("stock_quote"),)
        denials = ctx.get_denials(tools)
        assert "stock_quote" in denials[0].reason

    def test_multiple_denials(self):
        ctx = ToolPermissionContext.from_iterables(deny_prefixes=["db_"])
        tools = (make_tool("db_read"), make_tool("db_write"), make_tool("cache_get"))
        denials = ctx.get_denials(tools)
        assert len(denials) == 2


class TestCreateSecurePermissionContext:
    def test_default_allows_everything(self):
        ctx = create_secure_permission_context()
        assert ctx.blocks("stock_quote") is False
        assert ctx.blocks("db_query") is False
        assert ctx.blocks("alpaca_trade") is False

    def test_deny_database(self):
        ctx = create_secure_permission_context(allow_database=False)
        assert ctx.blocks("db_query") is True
        assert ctx.blocks("database_get") is True
        assert ctx.blocks("sql_execute") is True
        assert ctx.blocks("stock_quote") is False

    def test_deny_trading(self):
        ctx = create_secure_permission_context(allow_trading=False)
        assert ctx.blocks("alpaca_trade") is True
        assert ctx.blocks("submit_order") is True
        assert ctx.blocks("cancel_order") is True
        assert ctx.blocks("stock_quote") is False

    def test_deny_notifications(self):
        ctx = create_secure_permission_context(allow_notifications=False)
        assert ctx.blocks("notify_user") is True
        assert ctx.blocks("send_email_alert") is True
        assert ctx.blocks("alert_trigger") is True

    def test_deny_market_data(self):
        ctx = create_secure_permission_context(allow_market_data=False)
        assert ctx.blocks("quote_fetch") is True
        assert ctx.blocks("stock_price") is True
        assert ctx.blocks("market_status") is True

    def test_deny_multiple_categories(self):
        ctx = create_secure_permission_context(allow_database=False, allow_trading=False)
        assert ctx.blocks("db_query") is True
        assert ctx.blocks("alpaca_trade") is True
        assert ctx.blocks("stock_quote") is False

    def test_deny_all_categories(self):
        ctx = create_secure_permission_context(
            allow_database=False,
            allow_trading=False,
            allow_notifications=False,
            allow_market_data=False,
        )
        assert ctx.blocks("db_query") is True
        assert ctx.blocks("alpaca_trade") is True
        assert ctx.blocks("notify_user") is True
        assert ctx.blocks("stock_price") is True
