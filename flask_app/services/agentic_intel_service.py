"""
Silicon Oracle - Agentic Market Intelligence Service
Replaces the 4 sequential Gemini calls in MarketIntelligenceService
(market_analysis, recommendations, holdings_impact, watchlist) with a single
Google ADK agent loop that dynamically decides what data to fetch and synthesizes
a complete intelligence report in one reasoning pass.

The email HTML builder, scheduler, and all templates remain unchanged.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

REQUIRED_KEYS = {"market_analysis", "recommendations", "holdings_impact", "watchlist"}


class AgenticIntelService:
    """
    ADK-powered intelligence gatherer for market email alerts.

    Usage:
        svc = AgenticIntelService(config, user_id)
        intel = svc.generate_intelligence(holdings, risk_profile, cash, style, prev_report)
        # intel has keys: market_analysis, recommendations, holdings_impact, watchlist

    Raises on any failure so the caller can fall back to the sequential pipeline.
    """

    def __init__(self, config: dict[str, Any], user_id: str) -> None:
        self.config = config
        self.user_id = user_id
        if not config.get("GEMINI_API_KEY"):
            raise ValueError("GEMINI_API_KEY required for AgenticIntelService")

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def generate_intelligence(
        self,
        user_holdings: list[str],
        risk_profile: str,
        available_cash: float,
        trading_style: str,
        previous_report: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """
        Run the ADK agent and return a dict with keys:
            market_analysis, recommendations, holdings_impact, watchlist

        Raises on failure — caller wraps in try/except for fallback.
        """
        return asyncio.run(
            self._run_async(
                user_holdings=user_holdings,
                risk_profile=risk_profile,
                available_cash=available_cash,
                trading_style=trading_style,
                previous_report=previous_report,
            )
        )

    # ------------------------------------------------------------------ #
    # Async agent execution                                               #
    # ------------------------------------------------------------------ #

    async def _run_async(
        self,
        user_holdings: list[str],
        risk_profile: str,
        available_cash: float,
        trading_style: str,
        previous_report: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """
        Two-agent pipeline required because Gemini does not allow google_search
        (built-in grounding tool) and function calling in the same request.

        Agent 1 — macro_agent: google_search only → market_analysis JSON
        Agent 2 — holdings_agent: custom tools only → recommendations, holdings_impact, watchlist
        """
        import os

        # ADK reads GOOGLE_API_KEY (or GEMINI_API_KEY) from env — set it for this process
        api_key = self.config.get("GEMINI_API_KEY")
        os.environ["GOOGLE_API_KEY"] = api_key

        from google.adk.agents import LlmAgent
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.adk.tools import google_search
        from google.genai import types

        # Pre-fetch Oracle scores to embed in the holdings agent's prompt
        oracle_context = self._prefetch_oracle_scores(user_holdings)

        session_service = InMemorySessionService()

        # ------------------------------------------------------------------ #
        # Agent 1: Macro market analysis via Google Search                   #
        # ------------------------------------------------------------------ #
        macro_agent = LlmAgent(
            name="macro_agent",
            model="gemini-2.0-flash",
            instruction=self._build_macro_prompt(),
            tools=[google_search],
            generate_content_config=types.GenerateContentConfig(temperature=0.3),
        )

        macro_runner = Runner(
            agent=macro_agent,
            app_name="silicon_oracle_macro",
            session_service=session_service,
        )

        macro_session = await session_service.create_session(
            app_name="silicon_oracle_macro",
            user_id=self.user_id,
        )

        macro_message = types.Content(
            role="user",
            parts=[
                types.Part(
                    text=(
                        f"Today is {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p ET')}. "
                        "Search for today's major market developments and return ONLY the JSON report."
                    )
                )
            ],
        )

        market_analysis_text = ""
        async for event in macro_runner.run_async(
            user_id=self.user_id,
            session_id=macro_session.id,
            new_message=macro_message,
        ):
            if event.is_final_response() and event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        market_analysis_text += part.text

        if not market_analysis_text:
            raise ValueError("Macro agent returned empty response")

        market_analysis = self._parse_market_analysis(market_analysis_text)
        logger.info(
            "Macro agent done: sentiment=%s", market_analysis.get("market_sentiment", "?")
        )

        # ------------------------------------------------------------------ #
        # Agent 2: Holdings analysis via custom tools                        #
        # ------------------------------------------------------------------ #
        adk_tools = self._build_adk_tools()

        holdings_agent = LlmAgent(
            name="holdings_agent",
            model="gemini-2.0-flash",
            instruction=self._build_holdings_prompt(
                user_holdings=user_holdings,
                risk_profile=risk_profile,
                available_cash=available_cash,
                trading_style=trading_style,
                previous_report=previous_report,
                oracle_context=oracle_context,
            ),
            tools=adk_tools,
            generate_content_config=types.GenerateContentConfig(temperature=0.35),
        )

        holdings_runner = Runner(
            agent=holdings_agent,
            app_name="silicon_oracle_holdings",
            session_service=session_service,
        )

        holdings_session = await session_service.create_session(
            app_name="silicon_oracle_holdings",
            user_id=self.user_id,
        )

        holdings_message = types.Content(
            role="user",
            parts=[
                types.Part(
                    text=(
                        f"Today is {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p ET')}. "
                        f"MARKET CONTEXT FROM MACRO ANALYSIS:\n"
                        f"Sentiment: {market_analysis.get('market_sentiment')} ({market_analysis.get('sentiment_score')}/100)\n"
                        f"Summary: {market_analysis.get('market_summary', '')}\n"
                        f"Top catalysts: {', '.join(c.get('title','') for c in market_analysis.get('top_catalysts', [])[:3])}\n\n"
                        "Use your tools to analyze the holdings and return ONLY the JSON report."
                    )
                )
            ],
        )

        holdings_text = ""
        async for event in holdings_runner.run_async(
            user_id=self.user_id,
            session_id=holdings_session.id,
            new_message=holdings_message,
        ):
            if event.is_final_response() and event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        holdings_text += part.text

        if not holdings_text:
            raise ValueError("Holdings agent returned empty response")

        holdings_data = self._parse_holdings_data(holdings_text)
        logger.info(
            "Holdings agent done: recs=%d, impact=%d, watchlist=%d",
            len(holdings_data.get("recommendations", [])),
            len(holdings_data.get("holdings_impact", [])),
            len(holdings_data.get("watchlist", [])),
        )

        return {
            "market_analysis": market_analysis,
            "recommendations": holdings_data.get("recommendations", []),
            "holdings_impact": holdings_data.get("holdings_impact", []),
            "watchlist": holdings_data.get("watchlist", []),
        }

    # ------------------------------------------------------------------ #
    # ADK tool definitions                                                #
    # ------------------------------------------------------------------ #

    def _build_adk_tools(self) -> list:
        """
        Wrap existing AgentTool handlers as plain Python functions for ADK.
        Zero duplicate logic — all handlers come from build_execution_registry().
        """
        from flask_app.agent.execution_registry import ToolContext, build_execution_registry

        registry = build_execution_registry()
        ctx = ToolContext(user_id=self.user_id)

        def get_stock_quote(ticker: str) -> dict:
            """Get real-time price, change percentage, and volume for a stock ticker symbol."""
            result = registry.tool("stock_quote").execute({"ticker": ticker}, ctx)
            return result.get("result", result)

        def run_oracle_analysis(ticker: str) -> dict:
            """
            Run Oracle 15-factor technical analysis on a stock.
            Returns score (0-12), verdict (Strong Buy/Buy/Hold/Sell/Strong Sell),
            confidence percentage, and individual factor breakdown.
            """
            result = registry.tool("oracle_analysis").execute({"ticker": ticker}, ctx)
            return result.get("result", result)

        def fetch_stock_news(ticker: str) -> dict:
            """Fetch the latest news headlines and summaries for a stock ticker."""
            result = registry.tool("news_fetch").execute({"ticker": ticker}, ctx)
            return result.get("result", result)

        def get_portfolio_holdings() -> dict:
            """Get the user's current shadow portfolio holdings and recent trade history."""
            result = registry.tool("portfolio_value").execute({}, ctx)
            return result.get("result", result)

        def get_user_watchlist() -> dict:
            """Get the user's saved stock watchlists including custom and pre-configured lists."""
            result = registry.tool("watchlist_get").execute({}, ctx)
            return result.get("result", result)

        return [
            get_stock_quote,
            run_oracle_analysis,
            fetch_stock_news,
            get_portfolio_holdings,
            get_user_watchlist,
        ]

    # ------------------------------------------------------------------ #
    # Prompt builders                                                     #
    # ------------------------------------------------------------------ #

    def _build_macro_prompt(self) -> str:
        """System prompt for the macro agent (google_search only)."""
        return """You are a professional market analyst. Search for today's major market news and return a structured JSON analysis.

Search for:
1. Federal Reserve / interest rate decisions and commentary
2. Key macro data (inflation, GDP, unemployment, retail sales, consumer confidence)
3. Geopolitical events affecting markets (trade, conflicts, elections)
4. Major sector trends (AI, semiconductors, EV, energy, healthcare, crypto)
5. Market-moving corporate news (major earnings surprises, M&A, regulatory actions)
6. How major indices (S&P 500, Nasdaq, Dow) are moving

Return ONLY this JSON — no markdown, no preamble:

{
  "market_sentiment": "bullish|neutral|bearish",
  "sentiment_score": 0-100,
  "has_important_news": true,
  "top_catalysts": [
    {
      "title": "Specific headline",
      "impact": "high|medium|low",
      "category": "economic|geopolitical|sector|market",
      "sentiment": "positive|negative|neutral",
      "affected_sectors": ["Technology"],
      "summary": "2-3 sentence explanation with numbers and specifics",
      "source_url": "https://...",
      "source_name": "Reuters"
    }
  ],
  "key_risks": [{"risk": "", "severity": "high|medium|low", "timeframe": "immediate|short-term|long-term"}],
  "key_opportunities": [{"opportunity": "", "sectors": [], "timeframe": ""}],
  "sector_outlook": {
    "technology": "bullish|neutral|bearish - brief reason",
    "energy": "bullish|neutral|bearish - brief reason",
    "healthcare": "bullish|neutral|bearish - brief reason",
    "financials": "bullish|neutral|bearish - brief reason",
    "consumer": "bullish|neutral|bearish - brief reason",
    "industrials": "bullish|neutral|bearish - brief reason"
  },
  "recommended_actions": ["Action 1", "Action 2", "Action 3"],
  "market_summary": "3-4 sentence overall market overview"
}

Rules: has_important_news=true (markets always have relevant news). Include 3-7 catalysts, 2-5 risks, 2-5 opportunities. Return ONLY the JSON."""

    def _build_holdings_prompt(
        self,
        user_holdings: list[str],
        risk_profile: str,
        available_cash: float,
        trading_style: str,
        previous_report: dict[str, Any] | None,
        oracle_context: str,
    ) -> str:
        """System prompt for the holdings agent (custom tools only)."""
        holdings_str = ", ".join(user_holdings) if user_holdings else "none (all cash)"

        risk_desc = {
            "aggressive": "high-risk, high-reward growth stocks",
            "moderate": "balanced mix of growth and value, moderate risk",
            "conservative": "low-risk stable companies, dividends, minimal volatility",
        }.get(risk_profile.lower(), "balanced moderate risk")

        style_desc = {
            "day_trading": "intraday momentum plays, tight stops, same-day exits",
            "swing_trading": "2-10 day breakout and momentum setups",
            "long_term": "multi-month fundamental holds, ignore short-term noise",
        }.get(trading_style, "swing trading setups")

        ai_memory = ""
        if previous_report:
            prev_recs = ", ".join(
                f"{r.get('ticker')}({r.get('action')})"
                for r in previous_report.get("recommendations", [])[:5]
            )
            ai_memory = (
                f"\nAI MEMORY (previous report from {previous_report.get('timestamp', '?')}):\n"
                f"  Sentiment: {previous_report.get('sentiment_score', 50)}/100\n"
                f"  Previous recs: {prev_recs}\n"
                "  Note any meaningful changes since the last report."
            )

        return f"""You are a financial advisor analyzing stocks for a Silicon Oracle user.

USER PROFILE:
  Holdings: {holdings_str}
  Risk profile: {risk_profile.upper()} — {risk_desc}
  Trading style: {trading_style.replace('_', ' ').upper()} — {style_desc}
  Available cash: ${available_cash:,.2f}
{oracle_context}
{ai_memory}

AVAILABLE TOOLS:
- run_oracle_analysis(ticker): Get Oracle 15-factor technical score — call for each holding and any BUY candidates
- fetch_stock_news(ticker): Get latest news — call for holdings with negative signals
- get_stock_quote(ticker): Get live price — call when you need current price context

YOUR TASK:
1. Call run_oracle_analysis() for each of the user's holdings
2. Call fetch_stock_news() for any holding with Oracle verdict of SELL or weak score
3. Call run_oracle_analysis() for 2-3 potential BUY candidates based on the macro context you received
4. Synthesize all tool results into the JSON report below

Return ONLY this JSON — no markdown, no explanation:

{{
  "recommendations": [
    {{
      "ticker": "AAPL",
      "action": "BUY|HOLD|SELL",
      "priority": "high|medium|low",
      "confidence": 75,
      "reasoning": "2-3 sentences: Oracle score + specific macro catalyst + fit for trading style",
      "catalyst": "Specific named catalyst (never N/A)",
      "conflict_verdict": "fundamental_override|technical_conviction|risk_management|null",
      "conflict_reason": "One sentence if Oracle and action disagree, else null",
      "target_allocation": "20% of cash (BUY only)",
      "risk_level": "high|medium|low",
      "timeframe": "short-term|medium-term|long-term",
      "oracle_score": 8.5,
      "oracle_max": 12,
      "oracle_verdict": "Strong Buy",
      "oracle_confidence": 70
    }}
  ],
  "holdings_impact": [
    {{
      "ticker": "NVDA",
      "impact": "positive|negative|neutral",
      "severity": "high|medium|low",
      "explanation": "Which specific catalyst, mechanism of impact, what to watch next",
      "recommendation": "hold|reduce|add|sell"
    }}
  ],
  "watchlist": [
    {{
      "ticker": "META",
      "reason": "Why to watch — specific catalyst (1-2 sentences)",
      "watch_for": "What event or price level to wait for",
      "catalyst": "Specific catalyst name"
    }}
  ]
}}

Rules:
- BUY recs: tickers NOT in user holdings. HOLD/SELL: tickers IN user holdings
- Cover ALL holdings in holdings_impact
- Include 5-10 recommendations, 3-5 watchlist stocks
- Trading style {trading_style}: {style_desc}
- Return ONLY the JSON"""

    def _prefetch_oracle_scores(self, user_holdings: list[str]) -> str:
        """
        Pre-fetch Oracle scores for all holdings and embed them in the system prompt.
        This prevents the agent from making redundant oracle_analysis tool calls
        for basic holdings assessment, saving tokens and latency.
        """
        if not user_holdings:
            return ""

        try:
            from flask_app.agent.execution_registry import ToolContext, build_execution_registry

            registry = build_execution_registry()
            ctx = ToolContext(user_id=self.user_id)
            lines = ["\nPRE-FETCHED ORACLE SCORES (use as baseline for holdings assessment):"]

            for ticker in user_holdings[:12]:  # Cap to avoid prompt bloat
                result = registry.tool("oracle_analysis").execute({"ticker": ticker}, ctx)
                if result.get("success") and result.get("result"):
                    r = result["result"]
                    score = r.get("score", "?")
                    verdict = r.get("verdict", "?")
                    lines.append(f"  {ticker}: score={score}, verdict={verdict}")

            return "\n".join(lines)
        except Exception as exc:
            logger.warning(f"Oracle pre-fetch failed (non-fatal): {exc}")
            return ""


    # ------------------------------------------------------------------ #
    # Output parsing                                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_json(raw_text: str) -> dict[str, Any]:
        """Strip markdown fences and extract the outermost JSON object."""
        text = raw_text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s*```\s*$", "", text, flags=re.MULTILINE)
        text = text.strip()
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            text = json_match.group(0)
        return json.loads(text)

    def _parse_market_analysis(self, raw_text: str) -> dict[str, Any]:
        """Parse macro agent output. Raises on failure."""
        result = self._extract_json(raw_text)
        required = {"market_sentiment", "sentiment_score", "market_summary"}
        missing = required - result.keys()
        if missing:
            raise ValueError(f"Macro agent output missing: {missing}")
        # Ensure has_important_news defaults to True
        result.setdefault("has_important_news", True)
        return result

    def _parse_holdings_data(self, raw_text: str) -> dict[str, Any]:
        """Parse holdings agent output. Raises on failure."""
        result = self._extract_json(raw_text)
        for key in ("recommendations", "holdings_impact", "watchlist"):
            if not isinstance(result.get(key), list):
                result[key] = []
        return result
