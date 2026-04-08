from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from .execution_registry import AgentTool, ExecutionRegistry, build_execution_registry
from .permissions import PermissionDenial, ToolPermissionContext

logger = logging.getLogger(__name__)


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

        from .execution_registry import ToolContext

        ctx = ToolContext(user_id=self.user_id or "")
        return tool.execute(payload, ctx)

    def _get_gemini_client(self) -> Any | None:
        """Load the Gemini client using the current user's API key."""
        if not self.user_id:
            return None
        try:
            from utils import database as db
            from google import genai

            user_config = db.get_user_api_keys(self.user_id) or {}
            api_key = user_config.get("GEMINI_API_KEY")
            if not api_key:
                return None
            return genai.Client(api_key=api_key)
        except Exception as e:
            logger.warning(f"Could not load Gemini client: {e}")
            return None

    def _gemini_plan_tools(
        self, prompt: str, available_tools: tuple[AgentTool, ...]
    ) -> list[dict[str, Any]]:
        """
        Ask Gemini to decide which tools to call and with what arguments.
        Returns a list of {tool_name, payload} dicts.
        Falls back to empty list if Gemini is unavailable.
        """
        client = self._get_gemini_client()
        if not client:
            return []

        tool_descriptions = "\n".join(
            f"- {t.name}: {t.description}" for t in available_tools
        )

        planning_prompt = f"""You are an AI trading assistant with access to the following tools:

{tool_descriptions}

User request: "{prompt}"

Respond ONLY with a JSON array of tool calls needed to answer this request. Each item must have:
  - "tool_name": the exact tool name from the list above
  - "payload": a dict of arguments for that tool (use "ticker" for stock symbols, "trading_style" for style)

If no tools are needed, respond with an empty array [].
Extract any ticker symbol from the user's message (e.g. "analyze AAPL" → ticker: "AAPL").
Do not explain. Output only valid JSON.

Example: [{{"tool_name": "gemini_deep_analysis", "payload": {{"ticker": "AAPL", "trading_style": "swing_trading"}}}}]"""

        try:
            from google.genai import types

            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=planning_prompt,
                config=types.GenerateContentConfig(response_modalities=["TEXT"]),
            )
            raw = response.text.strip()
            # Strip markdown fences if present
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
        except Exception as e:
            logger.warning(f"Gemini tool planning failed: {e}")
        return []

    def _gemini_synthesize(
        self,
        prompt: str,
        tool_results: list[dict[str, Any]],
    ) -> str:
        """
        Ask Gemini to synthesize a final natural-language answer from tool results.
        Falls back to a formatted summary if Gemini is unavailable.
        """
        client = self._get_gemini_client()

        results_summary = json.dumps(
            [
                {
                    "tool": r.get("tool"),
                    "success": r.get("success"),
                    "result": r.get("result") if r.get("success") else r.get("error"),
                }
                for r in tool_results
            ],
            indent=2,
        )

        if not client:
            # Graceful fallback: plain text summary
            parts = []
            for r in tool_results:
                if r.get("success"):
                    parts.append(f"**{r.get('tool')}**: {r.get('result')}")
                else:
                    parts.append(f"**{r.get('tool')}** failed: {r.get('error')}")
            return "\n\n".join(parts) if parts else "No results available."

        synthesis_prompt = f"""You are a helpful AI trading assistant for Silicon Oracle.

The user asked: "{prompt}"

Here are the tool results:
{results_summary}

Write a clear, concise, conversational response to the user's question based on the tool results.
- Be specific: include prices, scores, verdicts, and key insights from the data.
- If analysis HTML is in the results, summarise it in plain text (no raw HTML).
- Keep it to 3-5 sentences unless the user asked for detail.
- Do not mention "tool results" or "JSON" — just answer naturally."""

        try:
            from google.genai import types

            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=synthesis_prompt,
                config=types.GenerateContentConfig(response_modalities=["TEXT"]),
            )
            return response.text.strip()
        except Exception as e:
            logger.warning(f"Gemini synthesis failed: {e}")
            parts = []
            for r in tool_results:
                if r.get("success"):
                    parts.append(f"{r.get('tool')}: {r.get('result')}")
                else:
                    parts.append(f"{r.get('tool')} error: {r.get('error')}")
            return "; ".join(parts) if parts else "No results available."

    def execute_turn(
        self,
        prompt: str,
        max_turns: int = 3,
        allow_writes: bool = False,
    ) -> AgentTurnResult:
        # --- Step 1: Ask Gemini to plan which tools to call ---
        available_tools = self.get_available_tools()
        planned_calls = self._gemini_plan_tools(prompt, available_tools)

        # --- Step 2: Fall back to keyword routing if Gemini planning returned nothing ---
        if not planned_calls:
            matches = self.route_prompt(prompt)
            allowed_matches, denials = self.filter_matches_by_permissions(matches)
            planned_calls = [
                {"tool_name": m.name, "payload": {"prompt": prompt}}
                for m in allowed_matches
                if m.kind == "tool"
            ]
        else:
            _, denials = self.filter_matches_by_permissions([])

        # --- Step 3: Execute planned tool calls ---
        tool_results: list[dict[str, Any]] = []
        matched_tool_names: list[str] = []
        matched_command_names: list[str] = []

        for call in planned_calls:
            tool_name = call.get("tool_name", "")
            payload = call.get("payload", {})

            if self.permission_context.blocks(tool_name):
                denials = tuple(list(denials) + [
                    PermissionDenial(
                        tool_name=tool_name,
                        reason=f"Tool '{tool_name}' is blocked by permission context",
                    )
                ])
                continue

            matched_tool_names.append(tool_name)
            result = self.execute_tool(tool_name, payload)
            tool_results.append(result)

        # --- Step 4: Synthesize a natural language answer with Gemini ---
        if tool_results:
            output = self._gemini_synthesize(prompt, tool_results)
        else:
            output = "I couldn't find relevant tools or data for that request."

        stop_reason = "completed" if len(tool_results) < max_turns else "max_turns_reached"

        return AgentTurnResult(
            output=output,
            matched_tools=tuple(matched_tool_names),
            matched_commands=tuple(matched_command_names),
            permission_denials=denials,
            stop_reason=stop_reason,
            tool_results=tuple(tool_results),
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
