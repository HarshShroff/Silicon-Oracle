from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .execution_registry import AgentTool, ExecutionRegistry, build_execution_registry
from .permissions import PermissionDenial, ToolPermissionContext


@dataclass(frozen=True)
class RoutedMatch:
    kind: str
    name: str
    description: str
    score: int


@dataclass
class AgentTurnResult:
    output: str
    matched_tools: tuple[str, ...]
    matched_commands: tuple[str, ...]
    permission_denials: tuple[PermissionDenial, ...]
    stop_reason: str = "completed"
    tool_results: tuple[dict[str, Any], ...] = ()


@dataclass
class AgentSession:
    session_id: str
    user_id: str
    messages: tuple[str, ...]
    tool_execution_results: tuple[dict[str, Any], ...] = ()
    created_at: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


class AgentRuntime:
    def __init__(
        self,
        registry: ExecutionRegistry,
        permission_context: ToolPermissionContext | None = None,
        user_id: str | None = None,
    ):
        self.registry = registry
        self.permission_context = permission_context or ToolPermissionContext()
        self.user_id = user_id

    def route_prompt(self, prompt: str, limit: int = 5) -> list[RoutedMatch]:
        tokens = {
            token.lower() for token in prompt.replace("/", " ").replace("-", " ").split() if token
        }

        tool_matches: list[RoutedMatch] = []
        command_matches: list[RoutedMatch] = []

        for tool in self.registry.tools:
            score = self._score(tokens, tool.name.lower(), tool.description.lower())
            if score > 0:
                tool_matches.append(
                    RoutedMatch(
                        kind="tool",
                        name=tool.name,
                        description=tool.description,
                        score=score,
                    )
                )

        for cmd in self.registry.commands:
            score = self._score(tokens, cmd.name.lower(), cmd.description.lower())
            if score > 0:
                command_matches.append(
                    RoutedMatch(
                        kind="command",
                        name=cmd.name,
                        description=cmd.description,
                        score=score,
                    )
                )

        tool_matches.sort(key=lambda x: (-x.score, x.name))
        command_matches.sort(key=lambda x: (-x.score, x.name))

        all_matches = tool_matches + command_matches
        all_matches.sort(key=lambda x: (-x.score, x.kind, x.name))

        return all_matches[:limit]

    def filter_matches_by_permissions(
        self, matches: list[RoutedMatch]
    ) -> tuple[list[RoutedMatch], tuple[PermissionDenial, ...]]:
        allowed = []
        denials = []

        for match in matches:
            if match.kind == "tool":
                if self.permission_context.blocks(match.name):
                    denials.append(
                        PermissionDenial(
                            tool_name=match.name,
                            reason=f"Tool '{match.name}' is blocked by permission context",
                        )
                    )
                else:
                    allowed.append(match)
            else:
                allowed.append(match)

        return allowed, tuple(denials)

    def execute_tool(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        tool = self.registry.tool(tool_name)
        if tool is None:
            return {
                "success": False,
                "tool": tool_name,
                "error": f"Unknown tool: {tool_name}",
                "error_type": "not_found",
            }

        if self.permission_context.blocks(tool_name):
            return {
                "success": False,
                "tool": tool_name,
                "error": f"Permission denied: tool '{tool_name}' is blocked",
                "error_type": "permission",
            }

        return tool.execute(payload)

    def execute_turn(
        self,
        prompt: str,
        max_turns: int = 3,
        allow_writes: bool = False,
    ) -> AgentTurnResult:
        matches = self.route_prompt(prompt)
        allowed_matches, denials = self.filter_matches_by_permissions(matches)

        tool_results = []
        matched_tool_names = []
        matched_command_names = []

        for match in allowed_matches:
            if match.kind == "tool":
                matched_tool_names.append(match.name)
                result = self.execute_tool(match.name, {"prompt": prompt})
                tool_results.append(result)
            else:
                matched_command_names.append(match.name)

        tool_results_tuple = tuple(tool_results)

        output_parts = []
        for result in tool_results_tuple:
            if result.get("success"):
                output_parts.append(f"{result.get('tool')}: {result.get('result')}")
            else:
                output_parts.append(f"{result.get('tool')} ERROR: {result.get('error')}")

        output = "; ".join(output_parts) if output_parts else "No tools matched"

        if allow_writes and not self.permission_context.blocks("any"):
            stop_reason = "max_turns_reached" if len(tool_results) >= max_turns else "completed"
        else:
            stop_reason = "read_only_mode"

        return AgentTurnResult(
            output=output,
            matched_tools=tuple(matched_tool_names),
            matched_commands=tuple(matched_command_names),
            permission_denials=denials,
            stop_reason=stop_reason,
            tool_results=tool_results_tuple,
        )

    def run_tool_loop(
        self,
        prompt: str,
        max_turns: int = 3,
    ) -> list[AgentTurnResult]:
        results = []
        for turn in range(max_turns):
            turn_prompt = prompt if turn == 0 else f"{prompt} [turn {turn + 1}]"
            result = self.execute_turn(turn_prompt, max_turns)
            results.append(result)
            if result.stop_reason != "completed":
                break
        return results

    def get_available_tools(self, category: str | None = None) -> tuple[AgentTool, ...]:
        tools = self.registry.tools
        tools = self.permission_context.filter_tools(tools)
        if category:
            tools = tuple(t for t in tools if t.category == category)
        return tools

    @staticmethod
    def _score(tokens: set[str], name: str, description: str) -> int:
        score = 0
        haystacks = [name, description]
        for token in tokens:
            if any(token in haystack for haystack in haystacks):
                score += 1
        return score


def build_agent_runtime(
    user_id: str | None = None,
    permission_context: ToolPermissionContext | None = None,
    extra_tools: tuple[AgentTool, ...] = (),
    extra_commands: tuple = (),
) -> AgentRuntime:
    registry = build_execution_registry(
        extra_tools=extra_tools,
        extra_commands=extra_commands,
    )
    return AgentRuntime(
        registry=registry,
        permission_context=permission_context,
        user_id=user_id,
    )
