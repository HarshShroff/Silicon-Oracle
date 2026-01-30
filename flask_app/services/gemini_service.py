"""
Silicon Oracle - Gemini AI Service
Handles communication with Google's Gemini AI for deep dive analysis
"""

import logging
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
from flask import current_app

logger = logging.getLogger(__name__)


class GeminiService:
    def __init__(self, config: Dict[str, str] = None):
        self.config = config or {}
        self.client = None
        self.model_name = "gemini-2.0-flash"
        self._init_client()

    def _init_client(self):
        """Initialize the Gemini client."""
        try:
            from google import genai

            api_key = self.config.get("GEMINI_API_KEY")

            if api_key:
                self.client = genai.Client(api_key=api_key)
            else:
                logger.warning("No Gemini API Key provided")

        except ImportError:
            logger.error("google-genai package not installed")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")

    def analyze_ticker(self, ticker: str) -> Tuple[str, int, str]:
        """
        Analyzes a stock using Google Search Grounding.
        Returns: (analysis_html, score, label)
        """
        if not self.client:
            return "<p>Gemini API not connected. Please add your API key in Settings.</p>", 0, "Error"

        try:
            from google.genai import types

            current_date = datetime.now().strftime("%B %d, %Y")

            # 1. Define the Grounding Tool
            google_search_tool = types.Tool(
                google_search=types.GoogleSearch()
            )

            # 2. The Prompt
            prompt = f"""
            Today is {current_date}.

            Perform a Google Search for the latest news, risks, and catalysts for {ticker} stock.

            Based on search results, provide a structured HTML analysis. Follow this EXACT template:

            <div class="space-y-3">
              <h4 class="text-sm font-semibold text-oracle-primary mb-1">Recent News (Last 7 Days)</h4>
              <p class="text-sm text-gray-200 leading-relaxed">2-3 most important developments with specific numbers...</p>

              <h4 class="text-sm font-semibold text-oracle-primary mb-1 mt-3">Bullish Catalysts</h4>
              <ul class="list-disc list-inside space-y-1 text-sm text-gray-200 ml-2">
                <li><strong class="text-white">Catalyst 1:</strong> Explanation with specifics...</li>
                <li><strong class="text-white">Catalyst 2:</strong> Explanation with specifics...</li>
              </ul>

              <h4 class="text-sm font-semibold text-oracle-primary mb-1 mt-3">Bearish Risks</h4>
              <ul class="list-disc list-inside space-y-1 text-sm text-gray-200 ml-2">
                <li><strong class="text-white">Risk 1:</strong> Explanation...</li>
                <li><strong class="text-white">Risk 2:</strong> Explanation...</li>
              </ul>

              <h4 class="text-sm font-semibold text-oracle-primary mb-1 mt-3">Bottom Line</h4>
              <p class="text-sm text-gray-200 leading-relaxed">One sentence overall outlook...</p>
            </div>

            CRITICAL RULES:
            - DO NOT use markdown (no ####, no **, no *, no ---)
            - ONLY use HTML tags exactly as shown in template above
            - DO NOT add ```html or ``` tags
            - Use <span class="text-green-400 font-semibold">+XX%</span> for positive numbers
            - Use <span class="text-red-400 font-semibold">-XX%</span> for negative numbers
            - Keep it concise - 2-3 sentences max per section

            At the very end, include these markers:
            {{SCORE:XX}} where XX is 0-100
            {{LABEL:YY}} where YY is Bullish, Neutral, or Bearish

            Example:
            {{SCORE:75}}
            {{LABEL:Bullish}}
            """

            # 3. Generate Content
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[google_search_tool],
                    response_modalities=["TEXT"],
                )
            )

            # 4. Extract Text
            analysis_html = response.text

            # Clean up markdown code blocks if present
            analysis_html = analysis_html.replace(
                "```html", "").replace("```", "")

            # 5. Parse Sentiment using structured markers
            import re
            score = 50  # default
            label = "Neutral"  # default

            # Extract score from {SCORE:XX} marker
            score_match = re.search(r"\{SCORE:(\d+)\}", analysis_html)
            if score_match:
                try:
                    score = int(score_match.group(1))
                    # Clamp score to 0-100 range
                    score = max(0, min(100, score))
                    # Remove marker from display
                    analysis_html = re.sub(r"\{SCORE:\d+\}", "", analysis_html)
                except ValueError:
                    pass

            # Extract label from {LABEL:XX} marker
            label_match = re.search(r"\{LABEL:(Bullish|Neutral|Bearish)\}", analysis_html, re.IGNORECASE)
            if label_match:
                label = label_match.group(1).capitalize()
                # Remove marker from display
                analysis_html = re.sub(r"\{LABEL:(Bullish|Neutral|Bearish)\}", "", analysis_html, flags=re.IGNORECASE)

            # Cleanup any extra whitespace from marker removal
            analysis_html = analysis_html.strip()

            return analysis_html, score, label

        except Exception as e:
            logger.error(f"Gemini analysis failed: {e}")
            return f"<p class='text-red-400'>AI Analysis Error: {str(e)}</p>", 0, "Error"

    def get_quick_insight(self, ticker: str) -> str:
        """
        Get a snappy 2-sentence AI insight for a stock.
        Optimized for the AI Guidance page Top Picks.
        """
        if not self.client:
            return "Gemini API Key Required"

        try:
            from google.genai import types

            # Simple prompt for speed and brevity
            prompt = f"Provide a snappy 2-sentence investment thesis for {ticker} stock based on most recent catalysts. Focus on momentum and risk. No markdown bolding, just plain text."

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )

            insight = response.text.strip()
            # Basic cleanup
            if len(insight) > 250:
                insight = insight[:247] + "..."

            return insight

        except Exception as e:
            logger.error(f"Quick insight failed for {ticker}: {e}")
            return "Insight currently unavailable."

    def get_factor_interpretation(self, ticker: str, oracle_data: Dict[str, Any]) -> str:
        """
        Get AI interpretation of Oracle's 15 quantitative factors.
        Explains WHY the score is what it is in plain English.

        Args:
            ticker: Stock ticker symbol
            oracle_data: Oracle score data with factors breakdown

        Returns:
            3-4 sentence interpretation
        """
        if not self.client:
            return "Gemini API Key Required"

        try:
            score = oracle_data.get("score", 0)
            max_score = oracle_data.get("max_score", 12)
            verdict = oracle_data.get("verdict_text", oracle_data.get("verdict", "Hold"))
            factors = oracle_data.get("factors", [])

            # Extract top bullish and bearish factors
            bullish_factors = [f for f in factors if f.get("signal") == "Bullish"][:3]
            bearish_factors = [f for f in factors if f.get("signal") == "Bearish"][:3]

            # Build factor summary
            bullish_summary = ", ".join([f"{f['name']}: {f['detail']}" for f in bullish_factors])
            bearish_summary = ", ".join([f"{f['name']}: {f['detail']}" for f in bearish_factors])

            prompt = f"""You are analyzing {ticker} stock's Oracle Score: {score:.1f}/{max_score} ({verdict}).

Bullish Factors: {bullish_summary if bullish_summary else "None"}
Bearish Factors: {bearish_summary if bearish_summary else "None"}

Provide a 3-4 sentence interpretation that:
1. Explains WHY the score is {score:.1f}/{max_score} in plain English
2. Highlights the strongest bullish signals (if any)
3. Warns about the biggest risks (if any)
4. Ends with a concise takeaway

Keep it conversational and actionable. No markdown formatting, just plain text."""

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )

            interpretation = response.text.strip()
            # Limit length
            if len(interpretation) > 400:
                interpretation = interpretation[:397] + "..."

            return interpretation

        except Exception as e:
            logger.error(f"Factor interpretation failed for {ticker}: {e}")
            return "Interpretation currently unavailable."

    def get_pattern_analysis(self, ticker: str) -> str:
        """
        Detect chart patterns and provide technical analysis.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Pattern analysis and predictions
        """
        if not self.client:
            return "Gemini API Key Required"

        try:
            from google.genai import types

            current_date = datetime.now().strftime("%B %d, %Y")

            prompt = f"""Today is {current_date}.

Analyze the recent price action and chart patterns for {ticker} stock.

Based on technical analysis principles, identify:
1. Any recognizable chart patterns (cup & handle, head & shoulders, triangle, breakout, etc.)
2. Key support and resistance levels
3. Momentum indicators (overbought/oversold conditions)
4. Short-term outlook (next 1-2 weeks)

Provide a 3-4 sentence technical summary. Focus on actionable insights.
No markdown formatting, just plain text."""

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )

            pattern_analysis = response.text.strip()
            # Limit length
            if len(pattern_analysis) > 400:
                pattern_analysis = pattern_analysis[:397] + "..."

            return pattern_analysis

        except Exception as e:
            logger.error(f"Pattern analysis failed for {ticker}: {e}")
            return "Pattern analysis currently unavailable."
