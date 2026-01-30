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
            
            Based *only* on the search results, provide:
            1. A brief summary of the most critical news from the last 7 days.
            2. Top 2 Bullish Catalysts.
            3. Top 2 Bearish Risks.
            4. A final Sentiment Score (0 to 100) and Label (Bullish/Bearish/Neutral).
            
            Format the output as clean HTML (without ```html tags). 
            Use <h4> for section headers, <ul>/<li> for lists, and <p> for paragraphs.
            Emphasize key points with <strong>.
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

            # 5. Parse Sentiment
            score = 50
            label = "Neutral"

            if "Score:" in analysis_html:
                try:
                    import re
                    match = re.search(r"Score:\s*(\d+)", analysis_html)
                    if match:
                        score = int(match.group(1))
                        if score > 60:
                            label = "Bullish"
                        elif score < 40:
                            label = "Bearish"
                except Exception:
                    pass

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
