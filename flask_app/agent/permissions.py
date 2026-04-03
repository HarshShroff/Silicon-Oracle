from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .execution_registry import AgentTool


@dataclass(frozen=True)
class PermissionDenial:
    tool_name: str
    reason: str


@dataclass(frozen=True)
class ToolPermissionContext:
    deny_names: frozenset[str] = field(default_factory=frozenset)
    deny_prefixes: tuple[str, ...] = ()

    @classmethod
    def from_iterables(
        cls, deny_names: list[str] | None = None, deny_prefixes: list[str] | None = None
    ) -> "ToolPermissionContext":
        return cls(
            deny_names=frozenset(name.lower() for name in (deny_names or [])),
            deny_prefixes=tuple(prefix.lower() for prefix in (deny_prefixes or [])),
        )

    def blocks(self, tool_name: str) -> bool:
        lowered = tool_name.lower()
        return lowered in self.deny_names or any(
            lowered.startswith(prefix) for prefix in self.deny_prefixes
        )

    def filter_tools(self, tools: tuple[AgentTool, ...]) -> tuple[AgentTool, ...]:
        return tuple(tool for tool in tools if not self.blocks(tool.name))

    def get_denials(self, tools: tuple[AgentTool, ...]) -> tuple[PermissionDenial, ...]:
        denials = []
        for tool in tools:
            if self.blocks(tool.name):
                denials.append(
                    PermissionDenial(
                        tool_name=tool.name,
                        reason=f"Tool '{tool.name}' is denied by permission context",
                    )
                )
        return tuple(denials)


def create_secure_permission_context(
    user_id: str | None = None,
    allow_database: bool = True,
    allow_trading: bool = True,
    allow_notifications: bool = True,
    allow_market_data: bool = True,
) -> ToolPermissionContext:
    deny_names = []
    deny_prefixes = []

    if not allow_database:
        deny_prefixes = (*deny_prefixes, "db_", "database_", "sql_")

    if not allow_trading:
        deny_names.extend(["alpaca_trade", "submit_order", "cancel_order"])

    if not allow_notifications:
        deny_prefixes = (*deny_prefixes, "notify_", "send_email", "alert_")

    if not allow_market_data:
        deny_prefixes = (*deny_prefixes, "quote_", "stock_", "market_")

    return ToolPermissionContext.from_iterables(deny_names, deny_prefixes)


__all__ = [
    "PermissionDenial",
    "ToolPermissionContext",
    "create_secure_permission_context",
]
