"""
Silicon Oracle - AI-Powered Market Intelligence Service
Scans broad financial/geopolitical news and generates personalized stock recommendations.
Uses Google Gemini AI with search grounding for comprehensive market analysis.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask_app.services.email_service import EmailService
from flask_app.services.gemini_service import GeminiService
from flask_app.services.oracle_service import OracleService
from flask_app.services.stock_service import StockService
from utils.database import get_latest_market_intelligence_report, save_market_intelligence_report

logger = logging.getLogger(__name__)


class MarketIntelligenceService:
    """
    AI-Powered Market Intelligence System that:
    1. Scans broad financial, geopolitical, and market-affecting news
    2. Uses AI to analyze impact on various sectors and stocks
    3. Generates personalized buy/hold/sell recommendations
    4. Considers user's risk profile, portfolio, and market conditions
    """

    # News categories to scan (broad topics, not specific stocks)
    NEWS_CATEGORIES = [
        # Financial & Economic
        "Federal Reserve interest rates",
        "inflation report",
        "GDP growth",
        "unemployment rate",
        "consumer confidence",
        "retail sales",
        "housing market",
        "oil prices",
        "dollar index",
        "bond yields treasury",
        # Geopolitical
        "US China relations trade",
        "Middle East conflict",
        "Russia Ukraine",
        "European Union economy",
        "elections United States",
        "global trade agreements",
        "sanctions international",
        # Sector Trends
        "artificial intelligence AI technology",
        "semiconductor chip shortage",
        "electric vehicle EV market",
        "renewable energy solar wind",
        "cryptocurrency bitcoin regulation",
        "healthcare biotech FDA",
        "cybersecurity data breach",
        "cloud computing",
        # Market Events
        "stock market rally crash",
        "bank crisis financial",
        "earnings season results",
        "IPO listings",
        "merger acquisition deal",
        "regulatory SEC investigation",
    ]

    def __init__(self, config: Optional[Dict[str, str]] = None):
        self.config = config or {}
        self.stock_service = StockService(config)
        self.oracle_service = OracleService(config)
        self.gemini_service = GeminiService(config)
        self.email_service = EmailService(config)

    def generate_market_intelligence(
        self,
        user_id: str,
        user_email: str,
        user_holdings: List[str],
        risk_profile: str = "moderate",
        available_cash: float = 0,
        hours_back: int = 1,
        trading_style: str = "swing_trading",
    ) -> bool:
        """
        Main entry point: Generate comprehensive market intelligence and recommendations.

        Args:
            user_id: User's ID for personalization
            user_email: Email to send report to
            user_holdings: List of tickers currently held
            risk_profile: aggressive, moderate, or conservative
            available_cash: Cash available for new positions
            hours_back: Hours of news to analyze

        Returns:
            True if email was sent, False otherwise
        """
        try:
            logger.info(f"Generating market intelligence for {user_email} (risk: {risk_profile})")

            # Step 0: Retrieve AI memory (previous market intelligence report)
            previous_report = get_latest_market_intelligence_report(user_id)
            if previous_report:
                logger.info(
                    f"Retrieved previous market intelligence from {previous_report.get('timestamp')}"
                )
            else:
                logger.info("No previous market intelligence found - first run for this user")

            # ------------------------------------------------------------------ #
            # AGENTIC PATH: single ADK agent loop replacing steps 1, 2, 3, 7     #
            # Falls back to sequential pipeline on any failure                   #
            # ------------------------------------------------------------------ #
            market_analysis = None
            recommendations = []
            holdings_impact = []
            watchlist = []

            try:
                from flask_app.services.agentic_intel_service import AgenticIntelService

                agentic_svc = AgenticIntelService(self.config, user_id)
                intel = agentic_svc.generate_intelligence(
                    user_holdings=user_holdings,
                    risk_profile=risk_profile,
                    available_cash=available_cash,
                    trading_style=trading_style,
                    previous_report=previous_report,
                )
                market_analysis = intel["market_analysis"]
                recommendations = intel["recommendations"]
                holdings_impact = intel["holdings_impact"]
                watchlist = intel["watchlist"]
                logger.info(
                    "Agentic path succeeded: sentiment=%s, recs=%d",
                    market_analysis.get("market_sentiment", "?"),
                    len(recommendations),
                )

            except Exception as agentic_err:
                logger.warning(
                    "ADK agent failed — falling back to sequential pipeline: %s", agentic_err
                )

                # ------------------------------------------------------------------ #
                # SEQUENTIAL FALLBACK: original 4-step pipeline (unchanged)         #
                # ------------------------------------------------------------------ #

                # Step 1: Get AI-powered market analysis
                market_analysis = self._get_comprehensive_market_analysis()

                if not market_analysis or not market_analysis.get("has_important_news"):
                    logger.info(f"No significant market developments for {user_email}")
                    return False

                # Step 2: Generate personalized stock recommendations (with AI memory)
                recommendations = self._generate_personalized_recommendations(
                    market_analysis=market_analysis,
                    user_holdings=user_holdings,
                    risk_profile=risk_profile,
                    available_cash=available_cash,
                    previous_report=previous_report,
                    trading_style=trading_style,
                )

                # Step 3: Analyze current holdings impact
                holdings_impact = self._analyze_holdings_impact(
                    user_holdings=user_holdings, market_analysis=market_analysis
                )

                # Step 7: Generate watchlist
                watchlist = self._generate_watchlist(
                    market_analysis=market_analysis,
                    user_holdings=user_holdings,
                    risk_profile=risk_profile,
                )

            # Early exits (apply to both paths)
            if not market_analysis or not market_analysis.get("has_important_news"):
                logger.info(f"No significant market developments for {user_email}")
                return False

            if not recommendations:
                logger.info(f"No actionable recommendations for {user_email}")
                return False

            # ------------------------------------------------------------------ #
            # Pure-Python steps — always run regardless of which path was used   #
            # ------------------------------------------------------------------ #

            # Step 4: Generate TL;DR summary
            tldr_summary = self._generate_tldr_summary(
                market_analysis=market_analysis,
                recommendations=recommendations,
                holdings_impact=holdings_impact,
            )
            logger.info(f"📌 TL;DR Summary generated: {tldr_summary}")
            logger.info(
                f"   Will show TL;DR? {bool(tldr_summary and tldr_summary.get('new_buys') is not None)}"
            )

            # Step 5: Calculate portfolio health metrics
            portfolio_health = self._calculate_portfolio_health(
                user_holdings=user_holdings, recommendations=recommendations
            )
            logger.info(f"📊 Portfolio Health calculated: {portfolio_health}")
            logger.info(
                f"   Will show Portfolio Health? {bool(portfolio_health and portfolio_health.get('total_positions') is not None)}"
            )

            # Step 6: Calculate stop-loss suggestions
            stop_losses = self._calculate_stop_losses(
                holdings_impact=holdings_impact, recommendations=recommendations
            )
            logger.info(f"🛑 Stop Losses calculated: {len(stop_losses)} positions")
            logger.info(f"   Stop loss details: {stop_losses}")

            logger.info(f"👀 Watchlist generated: {len(watchlist)} stocks")
            logger.info(f"   Will show Watchlist? {bool(watchlist)}")
            if watchlist:
                logger.info(f"   Watchlist items: {[w.get('ticker') for w in watchlist]}")

            # Step 8: Save market intelligence report for AI memory
            report_data = {
                "sentiment_score": market_analysis.get("sentiment_score", 50),
                "top_catalyst": market_analysis.get("top_catalysts", [{}])[0].get(
                    "title", "Market analysis"
                )
                if market_analysis.get("top_catalysts")
                else "Market analysis",
                "recommendations": [
                    {
                        "ticker": r.get("ticker"),
                        "action": r.get("action"),
                        "reasoning": r.get("reasoning", "")[:200],  # Store abbreviated reasoning
                    }
                    for r in recommendations[:10]  # Store top 10 recommendations
                ],
                "market_summary": market_analysis.get("market_summary", ""),
                "market_analysis": market_analysis,
                "holdings_impact": holdings_impact[:5] if holdings_impact else [],  # Store top 5
                "watchlist": watchlist[:5] if watchlist else [],  # Store top 5
            }

            save_success = save_market_intelligence_report(user_id, report_data)
            if save_success:
                logger.info(f"Market intelligence report saved for user {user_id}")
            else:
                logger.warning(f"Failed to save market intelligence report for user {user_id}")

            # Step 9: Send comprehensive intelligence email
            return self._send_intelligence_email(
                user_email=user_email,
                market_analysis=market_analysis,
                recommendations=recommendations,
                holdings_impact=holdings_impact,
                risk_profile=risk_profile,
                tldr_summary=tldr_summary,
                portfolio_health=portfolio_health,
                stop_losses=stop_losses,
                watchlist=watchlist,
            )

        except Exception as e:
            logger.error(f"Market intelligence generation failed: {e}", exc_info=True)
            return False

    def generate_market_close_summary(
        self,
        user_id: str,
        user_email: str,
        user_holdings: List[str],
        risk_profile: str = "moderate",
        available_cash: float = 0,
        trading_style: str = "swing_trading",
    ) -> bool:
        """
        Generate market close summary (5 PM email).
        Summarizes today's market performance and impact on shadow portfolio holdings.

        Args:
            user_id: User's ID for personalization
            user_email: Email to send report to
            user_holdings: List of tickers currently held in shadow portfolio
            risk_profile: aggressive, moderate, or conservative
            available_cash: Cash available for new positions
            trading_style: day_trading, swing_trading, or long_term

        Returns:
            True if email was sent, False otherwise
        """
        try:
            logger.info(f"Generating market close summary for {user_email}")

            # Get market close analysis
            market_analysis = self._get_market_close_analysis()

            if not market_analysis or not market_analysis.get("has_important_news"):
                logger.info(f"No significant market developments for {user_email}")
                return False

            # Analyze holdings impact with today's performance
            holdings_impact = self._analyze_holdings_impact(
                user_holdings=user_holdings, market_analysis=market_analysis
            )

            # Generate recommendations based on today's close
            recommendations = self._generate_personalized_recommendations(
                market_analysis=market_analysis,
                user_holdings=user_holdings,
                risk_profile=risk_profile,
                available_cash=available_cash,
                previous_report=None,
                trading_style=trading_style,
            )

            # Generate TL;DR summary
            tldr_summary = self._generate_tldr_summary(
                market_analysis=market_analysis,
                recommendations=recommendations,
                holdings_impact=holdings_impact,
            )

            # Calculate portfolio health
            portfolio_health = self._calculate_portfolio_health(
                user_holdings=user_holdings, recommendations=recommendations
            )

            # Calculate stop-losses
            stop_losses = self._calculate_stop_losses(
                holdings_impact=holdings_impact, recommendations=recommendations
            )

            # Send market close summary email
            subject = f"📊 Market Close Summary - {datetime.now().strftime('%b %d, %Y')}"

            html_body = self._build_market_close_email_html(
                market_analysis=market_analysis,
                recommendations=recommendations,
                holdings_impact=holdings_impact,
                risk_profile=risk_profile,
                tldr_summary=tldr_summary or {},
                portfolio_health=portfolio_health or {},
                stop_losses=stop_losses or {},
            )

            text_body = f"""
MARKET CLOSE SUMMARY - {datetime.now().strftime('%B %d, %Y')}
{'=' * 70}

{market_analysis.get('market_summary', 'No summary available')}

YOUR HOLDINGS IMPACT:
{chr(10).join([f"- {h.get('ticker')}: {h.get('impact', 'neutral').upper()} ({h.get('explanation', '')})" for h in holdings_impact[:5]])}

Powered by Silicon Oracle AI
            """

            success = self.email_service.send_email(
                to_email=user_email, subject=subject, html_body=html_body, text_body=text_body
            )

            if success:
                logger.info(f"Market close summary sent to {user_email}")
            else:
                logger.error(f"Failed to send market close summary to {user_email}")

            return success

        except Exception as e:
            logger.error(f"Market close summary generation failed: {e}", exc_info=True)
            return False

    def generate_market_preview(
        self,
        user_id: str,
        user_email: str,
        user_holdings: List[str],
        risk_profile: str = "moderate",
        available_cash: float = 0,
        trading_style: str = "swing_trading",
    ) -> bool:
        """
        Generate market preview (9 AM email).
        Provides heads up for today's market and potential impact on shadow portfolio.

        Args:
            user_id: User's ID for personalization
            user_email: Email to send report to
            user_holdings: List of tickers currently held in shadow portfolio
            risk_profile: aggressive, moderate, or conservative
            available_cash: Cash available for new positions
            trading_style: day_trading, swing_trading, or long_term

        Returns:
            True if email was sent, False otherwise
        """
        try:
            logger.info(f"Generating market preview for {user_email}")

            # Get market preview analysis
            market_analysis = self._get_market_preview_analysis()

            if not market_analysis or not market_analysis.get("has_important_news"):
                logger.info(f"No significant market events expected for {user_email}")
                return False

            # Analyze potential holdings impact
            holdings_impact = self._analyze_holdings_impact(
                user_holdings=user_holdings, market_analysis=market_analysis
            )

            # Generate recommendations for today
            recommendations = self._generate_personalized_recommendations(
                market_analysis=market_analysis,
                user_holdings=user_holdings,
                risk_profile=risk_profile,
                available_cash=available_cash,
                previous_report=None,
                trading_style=trading_style,
            )

            # Generate TL;DR summary
            tldr_summary = self._generate_tldr_summary(
                market_analysis=market_analysis,
                recommendations=recommendations,
                holdings_impact=holdings_impact,
            )

            # Calculate portfolio health
            portfolio_health = self._calculate_portfolio_health(
                user_holdings=user_holdings, recommendations=recommendations
            )

            # Send market preview email
            subject = f"🌅 Market Preview - {datetime.now().strftime('%b %d, %Y')}"

            html_body = self._build_market_preview_email_html(
                market_analysis=market_analysis,
                recommendations=recommendations,
                holdings_impact=holdings_impact,
                risk_profile=risk_profile,
                tldr_summary=tldr_summary or {},
                portfolio_health=portfolio_health or {},
            )

            text_body = f"""
MARKET PREVIEW - {datetime.now().strftime('%B %d, %Y')}
{'=' * 70}

TODAY'S OUTLOOK:
{market_analysis.get('market_summary', 'No preview available')}

POTENTIAL IMPACT ON YOUR HOLDINGS:
{chr(10).join([f"- {h.get('ticker')}: {h.get('impact', 'neutral').upper()} ({h.get('explanation', '')})" for h in holdings_impact[:5]])}

Powered by Silicon Oracle AI
            """

            success = self.email_service.send_email(
                to_email=user_email, subject=subject, html_body=html_body, text_body=text_body
            )

            if success:
                logger.info(f"Market preview sent to {user_email}")
            else:
                logger.error(f"Failed to send market preview to {user_email}")

            return success

        except Exception as e:
            logger.error(f"Market preview generation failed: {e}", exc_info=True)
            return False

    def _get_comprehensive_market_analysis(self) -> Dict[str, Any]:
        """
        Use Gemini AI with Google Search to analyze current market conditions.
        Returns comprehensive analysis of financial, geopolitical, and sector trends.
        """
        if not self.gemini_service.client:
            logger.warning("Gemini API not configured")
            return {"has_important_news": False}

        try:
            from google.genai import types

            current_date = datetime.now().strftime("%B %d, %Y")
            current_time = datetime.now().strftime("%I:%M %p")

            # Define Google Search tool for real-time news
            google_search_tool = types.Tool(google_search=types.GoogleSearch())

            prompt = f"""
Today is {current_date} at {current_time}.

You are a professional market analyst. Perform a comprehensive Google Search to analyze the current market environment.

Search for and analyze the following:
1. Latest Federal Reserve decisions, interest rates, inflation data
2. Major geopolitical events affecting markets (conflicts, elections, trade)
3. Key economic indicators (GDP, unemployment, consumer confidence, retail sales)
4. Significant sector trends (AI, semiconductors, EV, energy, healthcare, tech)
5. Major market movements, crashes, or rallies
6. Critical corporate news (major earnings surprises, M&A, regulatory actions)

Based on your search results, provide a structured analysis in this EXACT JSON format:

{{
  "market_sentiment": "bullish|neutral|bearish",
  "sentiment_score": 0-100,
  "has_important_news": true|false,
  "top_catalysts": [
    {{
      "title": "Catalyst headline",
      "impact": "high|medium|low",
      "category": "economic|geopolitical|sector|market",
      "sentiment": "positive|negative|neutral",
      "affected_sectors": ["Technology", "Energy", etc],
      "summary": "2-3 sentence explanation",
      "source_url": "https://example.com/article (the actual URL from your search results)",
      "source_name": "Source name (e.g., Reuters, Bloomberg, CNBC)"
    }}
  ],
  "key_risks": [
    {{
      "risk": "Risk description",
      "severity": "high|medium|low",
      "timeframe": "immediate|short-term|long-term"
    }}
  ],
  "key_opportunities": [
    {{
      "opportunity": "Opportunity description",
      "sectors": ["Sector names"],
      "timeframe": "immediate|short-term|long-term"
    }}
  ],
  "sector_outlook": {{
    "technology": "bullish|neutral|bearish - brief reason",
    "energy": "bullish|neutral|bearish - brief reason",
    "healthcare": "bullish|neutral|bearish - brief reason",
    "financials": "bullish|neutral|bearish - brief reason",
    "consumer": "bullish|neutral|bearish - brief reason",
    "industrials": "bullish|neutral|bearish - brief reason"
  }},
  "recommended_actions": [
    "Action 1 (e.g., Increase exposure to defensive sectors)",
    "Action 2",
    "Action 3"
  ],
  "market_summary": "3-4 sentence overall market outlook"
}}

CRITICAL RULES:
- ONLY return valid JSON, no markdown, no code blocks, no explanations
- has_important_news should be true if there are significant market-moving events
- Include 3-7 top catalysts
- Include 2-5 key risks
- Include 2-5 key opportunities
- Be specific with sector names and affected areas
- Base everything on real search results from today
- IMPORTANT: For each catalyst, include the source_url and source_name from your Google Search results so users can read the full articles
"""

            # Generate content with search grounding
            response = self.gemini_service.client.models.generate_content(
                model=self.gemini_service.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[google_search_tool],
                    response_modalities=["TEXT"],
                    temperature=0.3,  # Lower temperature for more factual analysis
                ),
            )

            # Parse JSON response
            import json
            import re

            response_text = response.text.strip()

            # Extract JSON from response (in case there's markdown)
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)

            analysis = json.loads(response_text)

            # Validate required fields
            if not isinstance(analysis, dict):
                raise ValueError("Invalid analysis format")

            logger.info(f"Market analysis complete: {analysis.get('market_sentiment')} sentiment")
            return analysis

        except Exception as e:
            logger.error(f"Market analysis failed: {e}", exc_info=True)
            return {"has_important_news": False}

    def _get_market_close_analysis(self) -> Dict[str, Any]:
        """
        Analyze today's market close performance.
        Focuses on what happened today and how markets performed.
        """
        if not self.gemini_service.client:
            logger.warning("Gemini API not configured")
            return {"has_important_news": False}

        try:
            from google.genai import types

            current_date = datetime.now().strftime("%B %d, %Y")
            current_time = datetime.now().strftime("%I:%M %p")

            google_search_tool = types.Tool(google_search=types.GoogleSearch())

            prompt = f"""
Today is {current_date} at {current_time} - Market Close Time.

You are a professional market analyst. Perform a comprehensive Google Search to analyze TODAY'S market performance.

Search for and analyze:
1. How major indices (S&P 500, Nasdaq, Dow) performed TODAY
2. Biggest winners and losers TODAY
3. Major news that moved markets TODAY
4. Key economic data releases TODAY
5. Significant sector performance TODAY
6. After-hours developments and earnings reports

Based on your search results, provide a structured analysis in this EXACT JSON format:

{{
  "market_sentiment": "bullish|neutral|bearish",
  "sentiment_score": 0-100,
  "has_important_news": true|false,
  "top_catalysts": [
    {{
      "title": "Catalyst headline from TODAY",
      "impact": "high|medium|low",
      "category": "economic|geopolitical|sector|market",
      "sentiment": "positive|negative|neutral",
      "affected_sectors": ["Technology", "Energy", etc],
      "summary": "2-3 sentence explanation of what happened TODAY",
      "source_url": "https://example.com/article",
      "source_name": "Source name"
    }}
  ],
  "key_risks": [
    {{
      "risk": "Risk that emerged TODAY",
      "severity": "high|medium|low",
      "timeframe": "immediate|short-term|long-term"
    }}
  ],
  "key_opportunities": [
    {{
      "opportunity": "Opportunity from TODAY's action",
      "sectors": ["Sector names"],
      "timeframe": "immediate|short-term|long-term"
    }}
  ],
  "sector_outlook": {{
    "technology": "bullish|neutral|bearish - TODAY's performance",
    "energy": "bullish|neutral|bearish - TODAY's performance",
    "healthcare": "bullish|neutral|bearish - TODAY's performance",
    "financials": "bullish|neutral|bearish - TODAY's performance",
    "consumer": "bullish|neutral|bearish - TODAY's performance",
    "industrials": "bullish|neutral|bearish - TODAY's performance"
  }},
  "recommended_actions": [
    "Action based on TODAY's close"
  ],
  "market_summary": "3-4 sentence summary of how markets performed TODAY"
}}

CRITICAL: Focus ONLY on TODAY's market performance, not predictions or forecasts.
Return ONLY valid JSON, no markdown.
"""

            response = self.gemini_service.client.models.generate_content(
                model=self.gemini_service.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[google_search_tool],
                    response_modalities=["TEXT"],
                    temperature=0.3,
                ),
            )

            import json
            import re

            response_text = response.text.strip()
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)

            analysis = json.loads(response_text)

            if not isinstance(analysis, dict):
                raise ValueError("Invalid analysis format")

            logger.info(
                f"Market close analysis complete: {analysis.get('market_sentiment')} sentiment"
            )
            return analysis

        except Exception as e:
            logger.error(f"Market close analysis failed: {e}", exc_info=True)
            return {"has_important_news": False}

    def _get_market_preview_analysis(self) -> Dict[str, Any]:
        """
        Analyze upcoming market events and provide preview for today.
        Focuses on what might happen and what to watch for.
        """
        if not self.gemini_service.client:
            logger.warning("Gemini API not configured")
            return {"has_important_news": False}

        try:
            from google.genai import types

            current_date = datetime.now().strftime("%B %d, %Y")
            current_time = datetime.now().strftime("%I:%M %p")

            google_search_tool = types.Tool(google_search=types.GoogleSearch())

            prompt = f"""
Today is {current_date} at {current_time} - Pre-Market Time.

You are a professional market analyst. Perform a comprehensive Google Search to preview TODAY's market.

Search for and analyze:
1. Economic data releases scheduled for TODAY
2. Major earnings reports expected TODAY
3. Fed speakers or policy announcements TODAY
4. Geopolitical events that could affect markets TODAY
5. Pre-market futures and Asian/European market performance
6. Key events to watch during TODAY's trading session

Based on your search results, provide a structured analysis in this EXACT JSON format:

{{
  "market_sentiment": "bullish|neutral|bearish",
  "sentiment_score": 0-100,
  "has_important_news": true|false,
  "top_catalysts": [
    {{
      "title": "Event happening TODAY",
      "impact": "high|medium|low",
      "category": "economic|geopolitical|sector|market",
      "sentiment": "positive|negative|neutral",
      "affected_sectors": ["Technology", "Energy", etc],
      "summary": "2-3 sentence explanation of what to expect TODAY",
      "source_url": "https://example.com/article",
      "source_name": "Source name"
    }}
  ],
  "key_risks": [
    {{
      "risk": "Risk to watch for TODAY",
      "severity": "high|medium|low",
      "timeframe": "immediate|short-term|long-term"
    }}
  ],
  "key_opportunities": [
    {{
      "opportunity": "Opportunity to watch for TODAY",
      "sectors": ["Sector names"],
      "timeframe": "immediate|short-term|long-term"
    }}
  ],
  "sector_outlook": {{
    "technology": "bullish|neutral|bearish - TODAY's outlook",
    "energy": "bullish|neutral|bearish - TODAY's outlook",
    "healthcare": "bullish|neutral|bearish - TODAY's outlook",
    "financials": "bullish|neutral|bearish - TODAY's outlook",
    "consumer": "bullish|neutral|bearish - TODAY's outlook",
    "industrials": "bullish|neutral|bearish - TODAY's outlook"
  }},
  "recommended_actions": [
    "Action to take or watch for TODAY"
  ],
  "market_summary": "3-4 sentence preview of what to expect in markets TODAY"
}}

CRITICAL: Focus on what will happen TODAY and what to watch for, not historical performance.
Return ONLY valid JSON, no markdown.
"""

            response = self.gemini_service.client.models.generate_content(
                model=self.gemini_service.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[google_search_tool],
                    response_modalities=["TEXT"],
                    temperature=0.3,
                ),
            )

            import json
            import re

            response_text = response.text.strip()
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)

            analysis = json.loads(response_text)

            if not isinstance(analysis, dict):
                raise ValueError("Invalid analysis format")

            logger.info(
                f"Market preview analysis complete: {analysis.get('market_sentiment')} sentiment"
            )
            return analysis

        except Exception as e:
            logger.error(f"Market preview analysis failed: {e}", exc_info=True)
            return {"has_important_news": False}

    def _generate_personalized_recommendations(
        self,
        market_analysis: Dict[str, Any],
        user_holdings: List[str],
        risk_profile: str,
        available_cash: float,
        previous_report: Optional[Dict[str, Any]] = None,
        trading_style: str = "swing_trading",
    ) -> List[Dict[str, Any]]:
        """
        Use AI to generate personalized stock recommendations based on:
        - Market analysis and catalysts
        - User's risk profile
        - Current holdings
        - Available cash
        NOW ORACLE-AWARE: Pre-calculates Oracle scores and provides them to AI
        so recommendations align with technical analysis.
        """
        if not self.gemini_service.client:
            return []

        try:
            import json

            from google.genai import types

            # Build context about user
            holdings_str = ", ".join(user_holdings) if user_holdings else "None (all cash)"

            risk_descriptions = {
                "aggressive": "high-risk, high-reward growth stocks with volatility",
                "moderate": "balanced mix of growth and value with moderate risk",
                "conservative": "low-risk, stable companies with dividends and minimal volatility",
            }
            risk_desc = risk_descriptions.get(risk_profile.lower(), risk_descriptions["moderate"])

            trading_style_descriptions = {
                "day_trading": "Intraday momentum plays. Focus on high-liquidity stocks with volume spikes and intraday catalysts. All timeframes MUST be 'short-term'. Avoid overnight holds. Prioritize stocks with clear entry/exit triggers within hours.",
                "swing_trading": "2-10 day setups based on technical breakouts, momentum shifts, and catalyst-driven moves. Timeframes should be 'short-term' or 'medium-term'. Look for stocks at key support/resistance with strong momentum potential.",
                "long_term": "Multi-month or multi-year fundamental holds. Focus on secular growth trends, strong balance sheets, competitive moats, and dividend quality. All timeframes MUST be 'long-term'. Ignore short-term volatility and noise.",
            }
            style_desc = trading_style_descriptions.get(
                trading_style, trading_style_descriptions["swing_trading"]
            )

            # Pre-calculate Oracle scores for user's holdings to inform AI
            holdings_oracle_context = ""
            if user_holdings:
                holdings_oracle_context = "\n\nORACLE TECHNICAL SCORES FOR YOUR HOLDINGS:"
                for ticker in user_holdings[:10]:  # Limit to avoid token bloat
                    try:
                        oracle_data = self.oracle_service.calculate_oracle_score(ticker)
                        score = oracle_data.get("score", 0)
                        max_score = oracle_data.get("max_score", 12)
                        verdict = oracle_data.get("verdict_text", "HOLD")
                        score_pct = (score / max_score * 100) if max_score > 0 else 0
                        holdings_oracle_context += f"\n- {ticker}: {score:.1f}/{max_score} ({score_pct:.0f}%) - Oracle says: {verdict}"
                    except Exception:
                        pass

            # Build AI memory context from previous report
            ai_memory_context = ""
            if previous_report:
                prev_timestamp = previous_report.get("timestamp", "Unknown")
                prev_sentiment = previous_report.get("sentiment_score", 50)
                prev_catalyst = previous_report.get("top_catalyst", "N/A")
                prev_summary = previous_report.get("market_summary", "")
                prev_recs = previous_report.get("recommendations", [])

                ai_memory_context = f"""

AI MEMORY - PREVIOUS ANALYSIS (from {prev_timestamp}):
- Previous Market Sentiment: {prev_sentiment}/100
- Previous Top Catalyst: {prev_catalyst}
- Previous Market Summary: {prev_summary[:300]}...
- Previous Recommendations: {', '.join([f"{r.get('ticker')} ({r.get('action')})" for r in prev_recs[:5]])}

USE THIS CONTEXT TO:
1. Identify changes in market conditions since last report
2. Track consistency/changes in your recommendations
3. Explain WHY your view has changed (or stayed the same)
4. Reference previous catalysts if they're still relevant
"""
            else:
                ai_memory_context = "\n\nAI MEMORY: This is your first analysis for this user. Provide comprehensive initial guidance."

            prompt = f"""
You are a financial advisor. Generate personalized stock recommendations by combining:
1. Market catalysts and macro conditions (provided below)
2. Oracle technical analysis scores (15-factor system: momentum, volatility, valuation, etc.)
3. User's risk profile and portfolio context

MARKET ANALYSIS:
{json.dumps(market_analysis, indent=2)}

USER PROFILE:
- Risk Profile: {risk_profile.upper()} ({risk_desc})
- Trading Style: {trading_style.replace('_', ' ').upper()} — {style_desc}
- Current Holdings: {holdings_str}
- Available Cash: ${available_cash:,.2f}
{holdings_oracle_context}
{ai_memory_context}

Generate 5-10 specific stock recommendations with DETAILED, ACTIONABLE reasoning.

Return ONLY valid JSON in this format:

{{
  "recommendations": [
    {{
      "ticker": "TICKER",
      "action": "BUY|HOLD|SELL",
      "priority": "high|medium|low",
      "confidence": 75,
      "reasoning": "2-3 sentences explaining: (1) Why this action NOW based on SPECIFIC market catalysts, (2) How Oracle technical score supports/conflicts with your decision, (3) What makes this suitable for user's risk profile. Be SPECIFIC - avoid generic phrases.",
      "catalyst": "Name the SPECIFIC market catalyst from the analysis above (e.g., 'Fed rate decision', 'China tariffs', 'Q4 earnings beat'). NEVER use 'N/A' or 'General market conditions'.",
      "conflict_verdict": "If Oracle and AI disagree, specify: 'fundamental_override' (news beats technicals), 'technical_conviction' (math beats noise), 'risk_management' (position sizing concerns), or null if no conflict",
      "conflict_reason": "If conflict exists, explain in 1 sentence WHY you chose fundamentals/technicals (e.g., 'Dollar surge invalidates oversold signals')",
      "target_allocation": "percentage of available cash (for BUY only)",
      "risk_level": "high|medium|low",
      "timeframe": "short-term|medium-term|long-term"
    }}
  ]
}}

NOTE: 'confidence' is 0-100 representing your confidence in this recommendation based on:
- How well Oracle score aligns with market catalysts (higher if aligned)
- Strength of market catalyst (stronger catalyst = higher confidence)
- Clarity of setup (clear entry/exit = higher confidence)
Example: Oracle Strong Buy + bullish catalyst + clear setup = 85-95% confidence

CRITICAL RULES:
1. For BUY recommendations: Only suggest tickers NOT in user's holdings
2. For HOLD recommendations: Only suggest tickers IN user's holdings that should be kept
3. For SELL recommendations: Only suggest tickers IN user's holdings that should be sold
4. Your ACTION should generally ALIGN with Oracle verdict unless you have strong market-based reasons to differ
5. When overriding Oracle (e.g., Oracle says Strong Buy but you say HOLD), you MUST:
   - Set conflict_verdict to "fundamental_override" (if news/catalysts win), "technical_conviction" (if Oracle math wins), or "risk_management" (if portfolio concerns win)
   - Set conflict_reason to explain in ONE sentence why (e.g., "Dollar surge invalidates oversold signals" or "Momentum still strong despite headline noise")
   - Include detailed explanation in reasoning field
6. NEVER use vague reasoning like "market sentiment" or "general conditions" - reference SPECIFIC catalysts
7. Every "catalyst" field must name a REAL catalyst from the market analysis - no placeholders
8. Match risk_level to user's risk profile: {risk_profile.upper()} = prefer {risk_desc}
9. TRADING STYLE ENFORCEMENT: User is a {trading_style.replace('_', ' ').upper()} trader. {style_desc} Every recommendation's timeframe and reasoning MUST align with this style. Do NOT suggest long-term holds to a day trader or intraday plays to a long-term investor.
10. Return ONLY valid JSON, no markdown, no code blocks

QUALITY EXAMPLES:
GOOD: "reasoning": "Oracle's Strong Buy (85%) aligns with bullish AI sector outlook. The government's push for manufacturing leadership and TSMC's dominant position in advanced chips makes this a hold despite near-term tariff risks. Matches moderate risk profile with established market leader."
BAD: "reasoning": "Given the moderate risk profile and current market sentiment, holding seems appropriate."

GOOD: "catalyst": "Union Budget STT hike on derivatives"
BAD: "catalyst": "N/A - General market conditions"
"""

            response = self.gemini_service.client.models.generate_content(
                model=self.gemini_service.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.4,  # Slightly higher for creative recommendations
                ),
            )

            # Parse JSON response
            import json
            import re

            response_text = response.text.strip()
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)

            recommendations_data = json.loads(response_text)
            recommendations = recommendations_data.get("recommendations", [])

            # Enrich with Oracle scores (for display in email)
            enriched = []
            for rec in recommendations:
                ticker = rec.get("ticker", "").upper()
                if not ticker:
                    continue

                try:
                    # Get Oracle score for this ticker
                    oracle_data = self.oracle_service.calculate_oracle_score(ticker)

                    enriched.append(
                        {
                            **rec,
                            "oracle_score": oracle_data.get("score", 0),
                            "oracle_max": oracle_data.get("max_score", 12),
                            "oracle_verdict": oracle_data.get("verdict_text", "HOLD"),
                            "oracle_confidence": oracle_data.get("confidence", 0),
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to get Oracle score for {ticker}: {e}")
                    enriched.append({**rec, "oracle_score": None})

            logger.info(f"Generated {len(enriched)} Oracle-aware personalized recommendations")
            return enriched

        except Exception as e:
            logger.error(f"Recommendation generation failed: {e}", exc_info=True)
            return []

    def _analyze_holdings_impact(
        self, user_holdings: List[str], market_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Analyze how current market conditions affect user's holdings.
        """
        if not user_holdings or not self.gemini_service.client:
            return []

        try:
            import json

            from google.genai import types

            holdings_str = ", ".join(user_holdings)

            prompt = f"""
Based on this market analysis:
{json.dumps(market_analysis, indent=2)}

Analyze how SPECIFIC market catalysts impact these holdings: {holdings_str}

For each ticker, provide DETAILED, ACTIONABLE analysis:

{{
  "holdings_impact": [
    {{
      "ticker": "TICKER",
      "impact": "positive|negative|neutral",
      "severity": "high|medium|low",
      "explanation": "2-3 sentences explaining: (1) Which SPECIFIC catalyst affects this stock and HOW, (2) Why this impact level, (3) What the user should watch for next. Be SPECIFIC - name catalysts, sectors, metrics.",
      "recommendation": "hold|reduce|add|sell"
    }}
  ]
}}

QUALITY RULES:
1. Name SPECIFIC catalysts in explanation (e.g., "STT hike on derivatives", "Fed rate pause", "China tariffs")
2. Explain the MECHANISM of impact - not just "affected by market conditions" but HOW and WHY
3. Be actionable - what should user watch for? (e.g., "Monitor Fed meeting March 15", "Watch for Q1 earnings Feb 20")
4. NEVER use vague phrases like "subject to market conditions" or "general sentiment"

GOOD EXAMPLE: "TSM benefits from AI chip demand surge mentioned in the semiconductor outlook. Taiwan's position in advanced chip manufacturing insulates it from derivative trading headwinds affecting financials. Watch for NVIDIA's upcoming earnings as a leading indicator for TSM demand."

BAD EXAMPLE: "TSM is subject to market conditions. Generally neutral outlook."

Return ONLY valid JSON, no markdown.
"""

            response = self.gemini_service.client.models.generate_content(
                model=self.gemini_service.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.3),
            )

            import json
            import re

            response_text = response.text.strip()
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)

            impact_data = json.loads(response_text)
            return impact_data.get("holdings_impact", [])

        except Exception as e:
            logger.error(f"Holdings impact analysis failed: {e}", exc_info=True)
            return []

    def _generate_tldr_summary(
        self,
        market_analysis: Dict[str, Any],
        recommendations: List[Dict[str, Any]],
        holdings_impact: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate concise TL;DR summary of key takeaways."""
        try:
            buy_recs = [r for r in recommendations if r.get("action") == "BUY"]
            sell_recs = [r for r in recommendations if r.get("action") == "SELL"]
            hold_recs = [r for r in recommendations if r.get("action") == "HOLD"]

            # Get top catalysts
            catalysts = market_analysis.get("top_catalysts", [])[:3]
            catalyst_summary = [c.get("title", "") for c in catalysts]

            # Get key risks
            risks = [c for c in catalysts if c.get("sentiment") == "negative"][:2]
            risk_summary = (
                [r.get("title", "") for r in risks] if risks else ["Monitor market volatility"]
            )

            # Holdings with highest impact
            high_impact = [h for h in holdings_impact if h.get("severity") == "high"][:2]

            return {
                "new_buys": len(buy_recs),
                "new_sells": len(sell_recs),
                "holds": len(hold_recs),
                "top_buy_tickers": [r.get("ticker") for r in buy_recs[:3]],
                "top_catalysts": catalyst_summary,
                "key_risks": risk_summary,
                "high_impact_holdings": [h.get("ticker") for h in high_impact],
            }
        except Exception as e:
            logger.error(f"TL;DR generation failed: {e}")
            return {}

    def _calculate_portfolio_health(
        self, user_holdings: List[str], recommendations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate portfolio health metrics including sector exposure and risk."""
        try:
            if not user_holdings:
                return {"total_positions": 0, "sectors": {}}

            # Simple sector mapping (expand this based on your needs)
            sector_map = {
                "TSM": "Technology",
                "NVDA": "Technology",
                "AAPL": "Technology",
                "MSFT": "Technology",
                "PPLT": "Commodities",
                "GLD": "Commodities",
                "GDX": "Commodities",
                "MP": "Materials",
                "SPYM": "Diversified",
                "BRK-B": "Financials",
                "JPM": "Financials",
                "BAC": "Financials",
                "MRK": "Healthcare",
                "JNJ": "Healthcare",
                "CAT": "Industrials",
                "SMCI": "Technology",
            }

            # Calculate sector exposure
            sectors: Dict[str, int] = {}
            for ticker in user_holdings:
                sector = sector_map.get(ticker, "Other")
                sectors[sector] = sectors.get(sector, 0) + 1

            # Calculate percentages
            total = len(user_holdings)
            sector_pct = {s: (count / total * 100) for s, count in sectors.items()}

            # Simple risk score based on Oracle scores
            total_risk_score = 0
            scored_count = 0
            for rec in recommendations:
                if rec.get("oracle_score"):
                    score_pct = (rec["oracle_score"] / rec.get("oracle_max", 12)) * 100
                    # Higher Oracle score = lower risk
                    risk_contribution = 100 - score_pct
                    total_risk_score += risk_contribution
                    scored_count += 1

            avg_risk = (total_risk_score / scored_count) if scored_count > 0 else 50

            return {
                "total_positions": total,
                "sectors": sector_pct,
                "risk_score": round(avg_risk / 10, 1),  # Scale to 0-10
                "concentration": max(sector_pct.values()) if sector_pct else 0,
            }
        except Exception as e:
            logger.error(f"Portfolio health calculation failed: {e}")
            return {}

    def _calculate_stop_losses(
        self, holdings_impact: List[Dict[str, Any]], recommendations: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Calculate Oracle-based stop-loss levels for holdings."""
        try:
            stop_losses = {}

            for rec in recommendations:
                if rec.get("action") in ["HOLD", "SELL"]:  # Only for held positions
                    ticker = rec.get("ticker")
                    oracle_score = rec.get("oracle_score")
                    oracle_max = rec.get("oracle_max", 12)

                    if oracle_score and ticker:
                        # Simple stop-loss: if Oracle score < 40%, suggest caution
                        score_pct = (oracle_score / oracle_max) * 100

                        if score_pct >= 70:
                            risk_level = "low"
                            suggestion = "Strong technical support - wide stop"
                        elif score_pct >= 50:
                            risk_level = "medium"
                            suggestion = "Moderate support - standard stop"
                        else:
                            risk_level = "high"
                            suggestion = "Weak technicals - tight stop recommended"

                        stop_losses[ticker] = {
                            "risk_level": risk_level,
                            "oracle_score_pct": score_pct,
                            "suggestion": suggestion,
                        }

            return stop_losses
        except Exception as e:
            logger.error(f"Stop-loss calculation failed: {e}")
            return {}

    def _generate_watchlist(
        self, market_analysis: Dict[str, Any], user_holdings: List[str], risk_profile: str
    ) -> List[Dict[str, Any]]:
        """Generate watchlist of stocks to monitor (not immediate buys)."""
        if not self.gemini_service.client:
            return []

        try:
            import json

            from google.genai import types

            holdings_str = ", ".join(user_holdings) if user_holdings else "None"

            prompt = f"""
Based on this market analysis:
{json.dumps(market_analysis, indent=2)}

Generate a watchlist of 3-5 stocks to MONITOR (not buy yet) for a {risk_profile.upper()} risk investor.
Holdings: {holdings_str}

Watchlist criteria:
- Stocks that could become buys if conditions improve
- Emerging opportunities tied to market catalysts
- Stocks showing technical setup but waiting for confirmation
- NOT currently in holdings

Return ONLY valid JSON:

{{
  "watchlist": [
    {{
      "ticker": "TICKER",
      "reason": "Why to watch this stock (1-2 sentences, specific catalyst)",
      "watch_for": "What event/price level to wait for before buying",
      "catalyst": "Specific market catalyst making this interesting"
    }}
  ]
}}

Return ONLY valid JSON, no markdown.
"""

            response = self.gemini_service.client.models.generate_content(
                model=self.gemini_service.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.5),
            )

            import json
            import re

            response_text = response.text.strip()
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)

            watchlist_data = json.loads(response_text)
            watchlist = watchlist_data.get("watchlist", [])

            logger.info(f"Generated watchlist with {len(watchlist)} stocks")
            return watchlist

        except Exception as e:
            logger.error(f"Watchlist generation failed: {e}", exc_info=True)
            return []

    def _send_intelligence_email(
        self,
        user_email: str,
        market_analysis: Dict[str, Any],
        recommendations: List[Dict[str, Any]],
        holdings_impact: List[Dict[str, Any]],
        risk_profile: str,
        tldr_summary: Optional[Dict[str, Any]] = None,
        portfolio_health: Optional[Dict[str, Any]] = None,
        stop_losses: Optional[Dict[str, Dict[str, Any]]] = None,
        watchlist: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """Send comprehensive market intelligence email with recommendations."""

        # Build subject line
        sentiment = market_analysis.get("market_sentiment", "neutral").upper()
        sentiment_emoji = "📈" if sentiment == "BULLISH" else "📉" if sentiment == "BEARISH" else "➡️"

        buy_count = len([r for r in recommendations if r.get("action") == "BUY"])
        sell_count = len([r for r in recommendations if r.get("action") == "SELL"])

        subject = f"{sentiment_emoji} Market Intel: {buy_count} BUY, {sell_count} SELL - {sentiment} Market"

        # Build HTML email
        html_body = self._build_intelligence_email_html(
            market_analysis=market_analysis,
            recommendations=recommendations,
            holdings_impact=holdings_impact,
            risk_profile=risk_profile,
            tldr_summary=tldr_summary or {},
            portfolio_health=portfolio_health or {},
            stop_losses=stop_losses or {},
            watchlist=watchlist or [],
        )

        # Build text email
        text_body = self._build_intelligence_email_text(
            market_analysis=market_analysis,
            recommendations=recommendations,
            holdings_impact=holdings_impact,
            tldr_summary=tldr_summary or {},
        )

        # Send email
        success = self.email_service.send_email(
            to_email=user_email, subject=subject, html_body=html_body, text_body=text_body
        )

        if success:
            logger.info(f"Market intelligence email sent to {user_email}")
        else:
            logger.error(f"Failed to send market intelligence email to {user_email}")

        return success

    def _build_intelligence_email_html(
        self,
        market_analysis: Dict[str, Any],
        recommendations: List[Dict[str, Any]],
        holdings_impact: List[Dict[str, Any]],
        risk_profile: str,
        tldr_summary: Dict[str, Any],
        portfolio_health: Dict[str, Any],
        stop_losses: Dict[str, Dict[str, Any]],
        watchlist: List[Dict[str, Any]],
    ) -> str:
        """Build HTML email for market intelligence with all enhanced features."""

        current_time = datetime.now().strftime("%B %d, %Y at %I:%M %p")

        sentiment = market_analysis.get("market_sentiment", "neutral")
        sentiment_score = market_analysis.get("sentiment_score", 50)
        market_summary = market_analysis.get("market_summary", "No summary available")

        sentiment_colors = {"bullish": "#059669", "neutral": "#0891b2", "bearish": "#dc2626"}
        sentiment_bg_colors = {"bullish": "#d1fae5", "neutral": "#cffafe", "bearish": "#fee2e2"}
        sentiment_color = sentiment_colors.get(sentiment.lower(), "#0891b2")
        sentiment_bg = sentiment_bg_colors.get(sentiment.lower(), "#cffafe")

        # Market overview section
        catalysts_html = ""
        for catalyst in market_analysis.get("top_catalysts", [])[:5]:
            impact_color = (
                "#dc2626"
                if catalyst.get("impact") == "high"
                else "#ea580c"
                if catalyst.get("impact") == "medium"
                else "#d97706"
            )
            sentiment_icon = (
                "📈"
                if catalyst.get("sentiment") == "positive"
                else "📉"
                if catalyst.get("sentiment") == "negative"
                else "➡️"
            )

            # Build source link if available
            source_html = ""
            if catalyst.get("source_url"):
                source_name = catalyst.get("source_name", "Read article")
                source_html = f"""
                <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #d1d5db;">
                    <a href="{catalyst.get('source_url')}" style="font-size: 11px; color: #2563eb; text-decoration: none; font-weight: 600;">
                        🔗 {source_name} →
                    </a>
                </div>
                """

            catalysts_html += f"""
            <div style="background-color: #f9fafb; padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 3px solid {impact_color};">
                <div style="display: flex; justify-content: between; margin-bottom: 6px;">
                    <span style="font-size: 12px; color: {impact_color}; font-weight: bold; text-transform: uppercase;">
                        {catalyst.get('impact', 'medium')} IMPACT {sentiment_icon}
                    </span>
                    <span style="font-size: 11px; color: #6b7280;">
                        {catalyst.get('category', 'market').upper()}
                    </span>
                </div>
                <h4 style="margin: 0 0 6px 0; font-size: 14px; color: #111827; font-weight: 600;">
                    {catalyst.get('title', 'Market Event')}
                </h4>
                <p style="margin: 0; font-size: 12px; color: #4b5563;">
                    {catalyst.get('summary', '')}
                </p>
                <p style="margin: 6px 0 0 0; font-size: 11px; color: #2563eb;">
                    Sectors: {', '.join(catalyst.get('affected_sectors', []))}
                </p>
                {source_html}
            </div>
            """

        # Recommendations section (grouped by action)
        buy_recs = [r for r in recommendations if r.get("action") == "BUY"]
        hold_recs = [r for r in recommendations if r.get("action") == "HOLD"]
        sell_recs = [r for r in recommendations if r.get("action") == "SELL"]

        def build_rec_card(rec, action_color):
            oracle_html = ""
            if rec.get("oracle_score") is not None:
                score = rec["oracle_score"]
                max_score = rec.get("oracle_max", 12)
                score_pct = (score / max_score * 100) if max_score > 0 else 0
                oracle_verdict = rec.get("oracle_verdict", "N/A").upper()
                ai_action = rec.get("action", "").upper()

                # Detect AI vs Oracle conflicts with enhanced verdict display
                conflict_verdict_html = ""

                # Check if rec has conflict verdict from AI
                conflict_verdict = rec.get("conflict_verdict")
                conflict_reason = rec.get("conflict_reason", "")

                # Also detect conflicts manually as fallback
                if "STRONG BUY" in oracle_verdict and ai_action in ["SELL", "HOLD"]:
                    if not conflict_verdict:
                        conflict_verdict = "fundamental_override"
                elif "SELL" in oracle_verdict and ai_action == "BUY":
                    if not conflict_verdict:
                        conflict_verdict = "technical_conviction"

                # Build conflict verdict box if there's a conflict
                if conflict_verdict:
                    verdict_labels = {
                        "fundamental_override": ("FUNDAMENTAL OVERRIDE", "#fef2f2", "#dc2626"),
                        "technical_conviction": ("TECHNICAL CONVICTION", "#f0fdf4", "#059669"),
                        "risk_management": ("RISK MANAGEMENT", "#fef9c3", "#d97706"),
                    }

                    verdict_label, verdict_bg, verdict_color = verdict_labels.get(
                        conflict_verdict, ("OVERRIDE", "#fef2f2", "#dc2626")
                    )

                    conflict_verdict_html = f"""
                    <div style="background-color: {verdict_bg}; border-left: 4px solid {verdict_color}; padding: 10px; margin-top: 10px; border-radius: 4px;">
                        <div style="font-size: 12px; font-weight: bold; color: {verdict_color}; margin-bottom: 4px;">
                            ⚖️ {verdict_label}
                        </div>
                        <div style="font-size: 11px; color: #374151; line-height: 1.5;">
                            {conflict_reason if conflict_reason else 'AI decision overrides Oracle score based on market fundamentals.'}
                        </div>
                        <div style="font-size: 10px; color: #6b7280; margin-top: 4px; font-style: italic;">
                            Oracle Score ({score_pct:.0f}%): {oracle_verdict} → OVERRIDDEN
                        </div>
                    </div>
                    """

                oracle_html = f"""
                <div style="margin-top: 8px; padding: 8px; background-color: #f3f4f6; border-radius: 4px; border: 1px solid #d1d5db;">
                    <span style="font-size: 11px; color: #6b7280;">Oracle Technical: </span>
                    <span style="font-size: 13px; font-weight: bold; color: {'#059669' if score_pct >= 70 else '#d97706' if score_pct >= 50 else '#dc2626'};">
                        {score:.1f}/{max_score} ({score_pct:.0f}%) - {oracle_verdict}
                    </span>
                </div>
                {conflict_verdict_html}
                """

            priority_colors = {"high": "#ef4444", "medium": "#f97316", "low": "#eab308"}
            priority_color = priority_colors.get(rec.get("priority", "medium").lower(), "#f97316")

            return f"""
            <div style="background-color: #f9fafb; padding: 14px; border-radius: 8px; margin-bottom: 10px; border-left: 4px solid {action_color}; border: 1px solid #e5e7eb;">
                <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
                    <h4 style="margin: 0; font-size: 18px; color: #111827; font-weight: 700;">
                        {rec.get('ticker', 'N/A')}
                    </h4>
                    <div style="text-align: right;">
                        <span style="background-color: {priority_color}20; color: {priority_color}; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold;">
                            {rec.get('priority', 'medium').upper()}
                        </span>
                        <div style="font-size: 11px; color: #6b7280; margin-top: 4px;">
                            Risk: {rec.get('risk_level', 'medium').upper()}
                        </div>
                        {f'<div style="font-size: 10px; color: {"#059669" if rec.get("confidence", 0) >= 75 else "#d97706" if rec.get("confidence", 0) >= 50 else "#dc2626"}; margin-top: 2px; font-weight: bold;">Confidence: {rec.get("confidence", 0)}%</div>' if rec.get('confidence') else ''}
                    </div>
                </div>
                <p style="margin: 0 0 8px 0; font-size: 13px; color: #4b5563;">
                    {rec.get('reasoning', 'No reasoning provided')}
                </p>
                <div style="display: flex; justify-content: space-between; font-size: 11px; color: #4f46e5;">
                    <span>💡 {rec.get('catalyst', 'Market conditions')}</span>
                    <span>⏱️ {rec.get('timeframe', 'medium-term')}</span>
                </div>
                {oracle_html}
            </div>
            """

        buy_html = "".join([build_rec_card(r, "#22c55e") for r in buy_recs[:5]])
        sell_html = "".join([build_rec_card(r, "#ef4444") for r in sell_recs[:5]])
        hold_html = "".join([build_rec_card(r, "#eab308") for r in hold_recs[:5]])

        # Watchlist section
        watchlist_html = ""
        for item in watchlist:
            watchlist_html += f"""
            <div style="background-color: #f9fafb; padding: 14px; border-radius: 8px; margin-bottom: 10px; border-left: 4px solid #a78bfa; border: 1px solid #e5e7eb;">
                <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
                    <h4 style="margin: 0; font-size: 16px; color: #111827; font-weight: 700;">
                        {item.get('ticker', 'N/A')}
                    </h4>
                    <span style="font-size: 10px; color: #7c3aed; text-transform: uppercase; background-color: #ede9fe; padding: 3px 8px; border-radius: 4px; font-weight: 600;">
                        Watch
                    </span>
                </div>
                <p style="margin: 0 0 8px 0; font-size: 13px; color: #4b5563;">
                    {item.get('reason', 'Emerging opportunity')}
                </p>
                <div style="background-color: #f3f4f6; padding: 6px 10px; border-radius: 4px; margin-bottom: 6px; border: 1px solid #d1d5db;">
                    <span style="font-size: 11px; color: #7c3aed; font-weight: bold;">
                        Wait for: {item.get('watch_for', 'Confirmation')}
                    </span>
                </div>
                <div style="font-size: 11px; color: #4f46e5;">
                    💡 {item.get('catalyst', 'Market catalyst')}
                </div>
            </div>
            """

        # Holdings impact section
        holdings_html = ""
        for holding in holdings_impact[:10]:
            impact_colors = {"positive": "#059669", "negative": "#dc2626", "neutral": "#6b7280"}
            impact_color = impact_colors.get(holding.get("impact", "neutral").lower(), "#6b7280")
            impact_icon = (
                "📈"
                if holding.get("impact") == "positive"
                else "📉"
                if holding.get("impact") == "negative"
                else "➡️"
            )

            ticker = holding.get("ticker", "N/A")
            stop_loss_info = stop_losses.get(ticker, {})
            stop_loss_html = ""
            if stop_loss_info:
                risk_colors = {"low": "#059669", "medium": "#d97706", "high": "#dc2626"}
                risk_color = risk_colors.get(stop_loss_info.get("risk_level", "medium"), "#d97706")
                stop_loss_html = f"""
                <div style="background-color: #fef3c7; padding: 6px 10px; border-radius: 4px; margin-top: 6px; border-left: 2px solid {risk_color}; border: 1px solid #fde68a;">
                    <span style="font-size: 10px; color: #6b7280;">Stop-Loss: </span>
                    <span style="font-size: 11px; color: {risk_color}; font-weight: bold;">
                        {stop_loss_info.get('suggestion', 'Monitor Oracle score')}
                    </span>
                    <span style="font-size: 10px; color: #6b7280;"> (Oracle: {stop_loss_info.get('oracle_score_pct', 0):.0f}%)</span>
                </div>
                """

            holdings_html += f"""
            <div style="background-color: #f9fafb; padding: 12px; border-radius: 8px; margin-bottom: 8px; border-left: 3px solid {impact_color}; border: 1px solid #e5e7eb;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <h4 style="margin: 0; font-size: 16px; color: #111827; font-weight: 700;">{ticker}</h4>
                    <span style="font-size: 12px; color: {impact_color}; font-weight: bold;">
                        {impact_icon} {holding.get('impact', 'neutral').upper()} ({holding.get('severity', 'medium')})
                    </span>
                </div>
                <p style="margin: 0 0 6px 0; font-size: 12px; color: #4b5563;">
                    {holding.get('explanation', 'No explanation available')}
                </p>
                <div style="background-color: #eff6ff; padding: 6px 10px; border-radius: 4px; border: 1px solid #bfdbfe;">
                    <span style="font-size: 11px; color: #1d4ed8; font-weight: bold;">
                        Recommendation: {holding.get('recommendation', 'hold').upper()}
                    </span>
                </div>
                {stop_loss_html}
            </div>
            """

        return f"""
        <html>
        <head>
            <meta name="color-scheme" content="light dark">
            <meta name="supported-color-schemes" content="light dark">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f5f5f5; color: #1a1a1a; padding: 20px; line-height: 1.6;">
            <div style="max-width: 750px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; padding: 28px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">

                <!-- Header -->
                <h1 style="color: #2563eb; margin: 0 0 6px 0; font-size: 26px; font-weight: 700;">🤖 AI Market Intelligence</h1>
                <p style="color: #6b7280; font-size: 13px; margin: 0 0 8px 0;">{current_time}</p>
                <p style="color: #4b5563; font-size: 12px; margin: 0 0 24px 0;">
                    Personalized for: <span style="color: #2563eb; font-weight: 600;">{risk_profile.upper()}</span> risk profile
                </p>

                <!-- TL;DR Summary -->
                {f'''
                <div style="background: #eff6ff; border: 2px solid #3b82f6; border-radius: 10px; padding: 18px; margin-bottom: 24px;">
                    <h2 style="color: #1e40af; margin: 0 0 14px 0; font-size: 18px; font-weight: 700;">📌 QUICK SUMMARY</h2>
                    <div style="display: grid; gap: 10px;">
                        <div style="font-size: 13px; color: #1f2937; line-height: 1.8;">
                            <strong style="color: #059669;">• {tldr_summary.get('new_buys', 0)} NEW BUYS:</strong> {', '.join(tldr_summary.get('top_buy_tickers', [])) if tldr_summary.get('top_buy_tickers') else 'None'}
                        </div>
                        <div style="font-size: 13px; color: #1f2937; line-height: 1.8;">
                            <strong style="color: #d97706;">• {tldr_summary.get('holds', 0)} HOLDS</strong>{f" - High impact on: {', '.join(tldr_summary.get('high_impact_holdings', []))}" if tldr_summary.get('high_impact_holdings') else ''}
                        </div>
                        <div style="font-size: 13px; color: #1f2937; line-height: 1.8;">
                            <strong style="color: #ea580c;">• KEY CATALYSTS:</strong> {'; '.join(tldr_summary.get('top_catalysts', ['None'])[:2])}
                        </div>
                        <div style="font-size: 13px; color: #1f2937; line-height: 1.8;">
                            <strong style="color: #dc2626;">• KEY RISKS:</strong> {'; '.join(tldr_summary.get('key_risks', ['Monitor volatility']))}
                        </div>
                    </div>
                </div>
                ''' if tldr_summary and tldr_summary.get('new_buys') is not None else ''}

                <!-- Portfolio Health -->
                {f'''
                <div style="background-color: #f9fafb; border: 1px solid #d1d5db; border-radius: 10px; padding: 18px; margin-bottom: 24px;">
                    <h2 style="color: #1e40af; margin: 0 0 14px 0; font-size: 18px; font-weight: 700;">📊 YOUR PORTFOLIO SNAPSHOT</h2>
                    <div style="display: grid; gap: 12px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-size: 13px; color: #4b5563;">Total Positions:</span>
                            <span style="font-size: 15px; font-weight: bold; color: #111827;">{portfolio_health.get('total_positions', 0)}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-size: 13px; color: #4b5563;">Portfolio Risk Score:</span>
                            <span style="font-size: 15px; font-weight: bold; color: {'#059669' if portfolio_health.get('risk_score', 5) < 4 else '#d97706' if portfolio_health.get('risk_score', 5) < 7 else '#dc2626'};">
                                {portfolio_health.get('risk_score', 5.0)}/10 ({'Low' if portfolio_health.get('risk_score', 5) < 4 else 'Moderate' if portfolio_health.get('risk_score', 5) < 7 else 'High'})
                            </span>
                        </div>
                        <div>
                            <div style="font-size: 12px; color: #4b5563; margin-bottom: 6px;">Sector Exposure:</div>
                            <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                                {' '.join([f'<span style="background-color: #e5e7eb; color: #374151; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: 500;">{sector}: {pct:.0f}%</span>' for sector, pct in portfolio_health.get('sectors', {}).items()]) if portfolio_health.get('sectors') else '<span style="color: #6b7280; font-size: 11px;">No positions</span>'}
                            </div>
                        </div>
                        {f'<div style="font-size: 12px; color: #ea580c; background-color: #fed7aa; padding: 8px; border-radius: 4px;"><strong>⚠️ Concentration Risk:</strong> {max(portfolio_health.get("sectors", {}).items(), key=lambda x: x[1])[0]} accounts for {max(portfolio_health.get("sectors", {}).values()):.0f}% of portfolio</div>' if portfolio_health.get('sectors') and portfolio_health.get('concentration', 0) > 40 else ''}
                    </div>
                </div>
                ''' if portfolio_health and portfolio_health.get('total_positions') is not None else ''}

                <!-- Market Sentiment Card -->
                <div style="background: {sentiment_bg}; border: 2px solid {sentiment_color}; border-radius: 10px; padding: 20px; margin-bottom: 24px;">
                    <div style="text-align: center;">
                        <h2 style="margin: 0 0 8px 0; font-size: 22px; color: {sentiment_color}; font-weight: 700;">
                            {sentiment.upper()} MARKET
                        </h2>
                        <div style="font-size: 48px; font-weight: bold; color: {sentiment_color}; margin: 8px 0;">
                            {sentiment_score}
                        </div>
                        <p style="margin: 12px 0 0 0; font-size: 14px; color: #1f2937; line-height: 1.6;">
                            {market_summary}
                        </p>
                    </div>
                </div>

                <!-- Key Market Catalysts -->
                <div style="margin-bottom: 28px;">
                    <h2 style="color: #d97706; font-size: 18px; margin: 0 0 14px 0; border-bottom: 2px solid #92400e; padding-bottom: 8px;">
                        🌍 Key Market Catalysts
                    </h2>
                    {catalysts_html}
                </div>

                <!-- Recommendations Explainer -->
                <div style="background-color: #dbeafe; border: 1px solid #3b82f6; border-radius: 8px; padding: 12px; margin-bottom: 24px;">
                    <p style="margin: 0; font-size: 12px; color: #1e40af; line-height: 1.5;">
                        <strong>💡 About Recommendations:</strong> AI analyzes market catalysts, geopolitics, and sector trends combined with Oracle's 15-factor technical analysis (momentum, volatility, valuation).
                        When AI and Oracle conflict, the reasoning explains why market conditions override technical signals. ⚠️ indicates disagreement.
                    </p>
                </div>

                <!-- BUY Recommendations -->
                {f'''
                <div style="margin-bottom: 28px;">
                    <h2 style="color: #059669; font-size: 18px; margin: 0 0 14px 0; border-bottom: 2px solid #065f46; padding-bottom: 8px;">
                        💰 BUY Recommendations ({len(buy_recs)})
                    </h2>
                    {buy_html}
                </div>
                ''' if buy_recs else ''}

                <!-- SELL Recommendations -->
                {f'''
                <div style="margin-bottom: 28px;">
                    <h2 style="color: #dc2626; font-size: 18px; margin: 0 0 14px 0; border-bottom: 2px solid #991b1b; padding-bottom: 8px;">
                        📤 SELL Recommendations ({len(sell_recs)})
                    </h2>
                    {sell_html}
                </div>
                ''' if sell_recs else ''}

                <!-- HOLD Recommendations -->
                {f'''
                <div style="margin-bottom: 28px;">
                    <h2 style="color: #d97706; font-size: 18px; margin: 0 0 14px 0; border-bottom: 2px solid #92400e; padding-bottom: 8px;">
                        🤝 HOLD Recommendations ({len(hold_recs)})
                    </h2>
                    {hold_html}
                </div>
                ''' if hold_recs else ''}

                <!-- Holdings Impact -->
                {f'''
                <div style="margin-bottom: 28px;">
                    <h2 style="color: #1d4ed8; font-size: 18px; margin: 0 0 14px 0; border-bottom: 2px solid #1e40af; padding-bottom: 8px;">
                        📊 Your Holdings Impact Analysis
                    </h2>
                    {holdings_html}
                </div>
                ''' if holdings_html else ''}

                <!-- Watchlist -->
                {f'''
                <div style="margin-bottom: 28px;">
                    <h2 style="color: #7c3aed; font-size: 18px; margin: 0 0 14px 0; border-bottom: 2px solid #6d28d9; padding-bottom: 8px;">
                        👀 WATCH LIST - Stocks to Monitor
                    </h2>
                    {watchlist_html if watchlist_html else '<p style="color: #6b7280; font-size: 13px; margin: 12px 0;">No watchlist stocks at this time.</p>'}
                </div>
                ''' if watchlist else ''}

                <!-- Footer -->
                <div style="margin-top: 32px; padding-top: 20px; border-top: 1px solid #d1d5db; text-align: center;">
                    <p style="color: #6b7280; font-size: 12px; margin: 0 0 6px 0;">
                        Powered by Silicon Oracle AI | Google Gemini + Oracle 15-Factor Analysis
                    </p>
                    <p style="color: #6b7280; font-size: 11px; margin: 0;">
                        ⚠️ This is AI-generated guidance. Always do your own research before investing.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

    def _build_intelligence_email_text(
        self,
        market_analysis: Dict[str, Any],
        recommendations: List[Dict[str, Any]],
        holdings_impact: List[Dict[str, Any]],
        tldr_summary: Dict[str, Any],
    ) -> str:
        """Build plain text email with TL;DR."""

        text = f"""
AI MARKET INTELLIGENCE REPORT
{datetime.now().strftime('%B %d, %Y at %I:%M %p')}
{'=' * 70}

MARKET SENTIMENT: {market_analysis.get('market_sentiment', 'neutral').upper()}
Score: {market_analysis.get('sentiment_score', 50)}/100

{market_analysis.get('market_summary', 'No summary available')}

{'=' * 70}
KEY CATALYSTS
{'=' * 70}
"""
        for idx, catalyst in enumerate(market_analysis.get("top_catalysts", [])[:5], 1):
            text += f"\n{idx}. [{catalyst.get('impact', 'medium').upper()}] {catalyst.get('title', 'Event')}\n"
            text += f"   {catalyst.get('summary', '')}\n"
            text += f"   Sectors: {', '.join(catalyst.get('affected_sectors', []))}\n"

        # BUY recommendations
        buy_recs = [r for r in recommendations if r.get("action") == "BUY"]
        if buy_recs:
            text += f"\n\n{'=' * 70}\nBUY RECOMMENDATIONS ({len(buy_recs)})\n{'=' * 70}\n"
            for idx, rec in enumerate(buy_recs, 1):
                text += f"\n{idx}. {rec.get('ticker', 'N/A')} - {rec.get('priority', 'medium').upper()} PRIORITY\n"
                text += f"   {rec.get('reasoning', '')}\n"
                if rec.get("oracle_score"):
                    text += f"   Oracle: {rec['oracle_score']:.1f}/{rec.get('oracle_max', 12)} - {rec.get('oracle_verdict', 'N/A')}\n"

        # SELL recommendations
        sell_recs = [r for r in recommendations if r.get("action") == "SELL"]
        if sell_recs:
            text += f"\n\n{'=' * 70}\nSELL RECOMMENDATIONS ({len(sell_recs)})\n{'=' * 70}\n"
            for idx, rec in enumerate(sell_recs, 1):
                text += f"\n{idx}. {rec.get('ticker', 'N/A')} - {rec.get('priority', 'medium').upper()} PRIORITY\n"
                text += f"   {rec.get('reasoning', '')}\n"

        # Holdings impact
        if holdings_impact:
            text += f"\n\n{'=' * 70}\nYOUR HOLDINGS IMPACT\n{'=' * 70}\n"
            for holding in holdings_impact:
                text += f"\n{holding.get('ticker', 'N/A')}: {holding.get('impact', 'neutral').upper()} ({holding.get('severity', 'medium')})\n"
                text += f"   {holding.get('explanation', '')}\n"
                text += f"   Recommendation: {holding.get('recommendation', 'hold').upper()}\n"

        text += "\n\n" + "=" * 70
        text += "\nPowered by Silicon Oracle AI"
        text += "\n⚠️ This is AI-generated guidance. Always do your own research."

        return text

    def _build_market_close_email_html(
        self,
        market_analysis: Dict[str, Any],
        recommendations: List[Dict[str, Any]],
        holdings_impact: List[Dict[str, Any]],
        risk_profile: str,
        tldr_summary: Dict[str, Any],
        portfolio_health: Dict[str, Any],
        stop_losses: Dict[str, Dict[str, Any]],
    ) -> str:
        """Build HTML email for market close summary (5 PM email)."""

        current_time = datetime.now().strftime("%B %d, %Y at %I:%M %p")

        sentiment = market_analysis.get("market_sentiment", "neutral")
        sentiment_score = market_analysis.get("sentiment_score", 50)
        market_summary = market_analysis.get("market_summary", "No summary available")

        sentiment_colors = {"bullish": "#059669", "neutral": "#0891b2", "bearish": "#dc2626"}
        sentiment_bg_colors = {"bullish": "#d1fae5", "neutral": "#cffafe", "bearish": "#fee2e2"}
        sentiment_color = sentiment_colors.get(sentiment.lower(), "#0891b2")
        sentiment_bg = sentiment_bg_colors.get(sentiment.lower(), "#cffafe")

        # Build catalysts HTML
        catalysts_html = ""
        for catalyst in market_analysis.get("top_catalysts", [])[:5]:
            impact_color = (
                "#dc2626"
                if catalyst.get("impact") == "high"
                else "#ea580c"
                if catalyst.get("impact") == "medium"
                else "#d97706"
            )
            sentiment_icon = (
                "📈"
                if catalyst.get("sentiment") == "positive"
                else "📉"
                if catalyst.get("sentiment") == "negative"
                else "➡️"
            )

            source_html = ""
            if catalyst.get("source_url"):
                source_name = catalyst.get("source_name", "Read article")
                source_html = f"""
                <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #d1d5db;">
                    <a href="{catalyst.get('source_url')}" style="font-size: 11px; color: #2563eb; text-decoration: none; font-weight: 600;">
                        🔗 {source_name} →
                    </a>
                </div>
                """

            catalysts_html += f"""
            <div style="background-color: #f9fafb; padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 3px solid {impact_color};">
                <div style="display: flex; justify-content: between; margin-bottom: 6px;">
                    <span style="font-size: 12px; color: {impact_color}; font-weight: bold; text-transform: uppercase;">
                        {catalyst.get('impact', 'medium')} IMPACT {sentiment_icon}
                    </span>
                </div>
                <h4 style="margin: 0 0 6px 0; font-size: 14px; color: #111827; font-weight: 600;">
                    {catalyst.get('title', 'Market Event')}
                </h4>
                <p style="margin: 0; font-size: 12px; color: #4b5563;">
                    {catalyst.get('summary', '')}
                </p>
                {source_html}
            </div>
            """

        # Holdings impact HTML
        holdings_html = ""
        for holding in holdings_impact[:10]:
            impact_colors = {"positive": "#059669", "negative": "#dc2626", "neutral": "#6b7280"}
            impact_color = impact_colors.get(holding.get("impact", "neutral").lower(), "#6b7280")
            impact_icon = (
                "📈"
                if holding.get("impact") == "positive"
                else "📉"
                if holding.get("impact") == "negative"
                else "➡️"
            )

            ticker = holding.get("ticker", "N/A")
            stop_loss_info = stop_losses.get(ticker, {})
            stop_loss_html = ""
            if stop_loss_info:
                risk_colors = {"low": "#059669", "medium": "#d97706", "high": "#dc2626"}
                risk_color = risk_colors.get(stop_loss_info.get("risk_level", "medium"), "#d97706")
                stop_loss_html = f"""
                <div style="background-color: #fef3c7; padding: 6px 10px; border-radius: 4px; margin-top: 6px; border-left: 2px solid {risk_color};">
                    <span style="font-size: 10px; color: #6b7280;">Stop-Loss: </span>
                    <span style="font-size: 11px; color: {risk_color}; font-weight: bold;">
                        {stop_loss_info.get('suggestion', 'Monitor Oracle score')}
                    </span>
                </div>
                """

            holdings_html += f"""
            <div style="background-color: #f9fafb; padding: 12px; border-radius: 8px; margin-bottom: 8px; border-left: 3px solid {impact_color};">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <h4 style="margin: 0; font-size: 16px; color: #111827; font-weight: 700;">{ticker}</h4>
                    <span style="font-size: 12px; color: {impact_color}; font-weight: bold;">
                        {impact_icon} {holding.get('impact', 'neutral').upper()}
                    </span>
                </div>
                <p style="margin: 0 0 6px 0; font-size: 12px; color: #4b5563;">
                    {holding.get('explanation', 'No explanation available')}
                </p>
                {stop_loss_html}
            </div>
            """

        return f"""
        <html>
        <head>
            <meta name="color-scheme" content="light dark">
            <meta name="supported-color-schemes" content="light dark">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f5f5f5; color: #1a1a1a; padding: 20px; line-height: 1.6;">
            <div style="max-width: 750px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; padding: 28px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">

                <!-- Header -->
                <h1 style="color: #2563eb; margin: 0 0 6px 0; font-size: 26px; font-weight: 700;">📊 Market Close Summary</h1>
                <p style="color: #6b7280; font-size: 13px; margin: 0 0 24px 0;">{current_time}</p>

                <!-- Market Sentiment Card -->
                <div style="background: {sentiment_bg}; border: 2px solid {sentiment_color}; border-radius: 10px; padding: 20px; margin-bottom: 24px;">
                    <div style="text-align: center;">
                        <h2 style="margin: 0 0 8px 0; font-size: 22px; color: {sentiment_color}; font-weight: 700;">
                            TODAY'S MARKET: {sentiment.upper()}
                        </h2>
                        <div style="font-size: 48px; font-weight: bold; color: {sentiment_color}; margin: 8px 0;">
                            {sentiment_score}
                        </div>
                        <p style="margin: 12px 0 0 0; font-size: 14px; color: #1f2937; line-height: 1.6;">
                            {market_summary}
                        </p>
                    </div>
                </div>

                <!-- Today's Key Events -->
                <div style="margin-bottom: 28px;">
                    <h2 style="color: #d97706; font-size: 18px; margin: 0 0 14px 0; border-bottom: 2px solid #92400e; padding-bottom: 8px;">
                        📰 What Moved Markets Today
                    </h2>
                    {catalysts_html}
                </div>

                <!-- Portfolio Impact -->
                {f'''
                <div style="margin-bottom: 28px;">
                    <h2 style="color: #1d4ed8; font-size: 18px; margin: 0 0 14px 0; border-bottom: 2px solid #1e40af; padding-bottom: 8px;">
                        💼 Impact on Your Shadow Portfolio
                    </h2>
                    {holdings_html}
                </div>
                ''' if holdings_html else ''}

                <!-- Portfolio Health -->
                {f'''
                <div style="background-color: #f9fafb; border: 1px solid #d1d5db; border-radius: 10px; padding: 18px; margin-bottom: 24px;">
                    <h2 style="color: #1e40af; margin: 0 0 14px 0; font-size: 18px; font-weight: 700;">📊 Portfolio Snapshot</h2>
                    <div style="display: grid; gap: 12px;">
                        <div style="display: flex; justify-content: space-between;">
                            <span style="font-size: 13px; color: #4b5563;">Total Positions:</span>
                            <span style="font-size: 15px; font-weight: bold;">{portfolio_health.get('total_positions', 0)}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between;">
                            <span style="font-size: 13px; color: #4b5563;">Risk Score:</span>
                            <span style="font-size: 15px; font-weight: bold; color: {'#059669' if portfolio_health.get('risk_score', 5) < 4 else '#d97706' if portfolio_health.get('risk_score', 5) < 7 else '#dc2626'};">
                                {portfolio_health.get('risk_score', 5.0)}/10
                            </span>
                        </div>
                    </div>
                </div>
                ''' if portfolio_health and portfolio_health.get('total_positions') is not None else ''}

                <!-- Footer -->
                <div style="margin-top: 32px; padding-top: 20px; border-top: 1px solid #d1d5db; text-align: center;">
                    <p style="color: #6b7280; font-size: 12px; margin: 0 0 6px 0;">
                        Powered by Silicon Oracle AI | Market Close Summary (5 PM)
                    </p>
                    <p style="color: #6b7280; font-size: 11px; margin: 0;">
                        ⚠️ This is AI-generated guidance. Always do your own research.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

    def _build_market_preview_email_html(
        self,
        market_analysis: Dict[str, Any],
        recommendations: List[Dict[str, Any]],
        holdings_impact: List[Dict[str, Any]],
        risk_profile: str,
        tldr_summary: Dict[str, Any],
        portfolio_health: Dict[str, Any],
    ) -> str:
        """Build HTML email for market preview (9 AM email)."""

        current_time = datetime.now().strftime("%B %d, %Y at %I:%M %p")

        sentiment = market_analysis.get("market_sentiment", "neutral")
        sentiment_score = market_analysis.get("sentiment_score", 50)
        market_summary = market_analysis.get("market_summary", "No preview available")

        sentiment_colors = {"bullish": "#059669", "neutral": "#0891b2", "bearish": "#dc2626"}
        sentiment_bg_colors = {"bullish": "#d1fae5", "neutral": "#cffafe", "bearish": "#fee2e2"}
        sentiment_color = sentiment_colors.get(sentiment.lower(), "#0891b2")
        sentiment_bg = sentiment_bg_colors.get(sentiment.lower(), "#cffafe")

        # Build catalysts HTML (what to watch for)
        catalysts_html = ""
        for catalyst in market_analysis.get("top_catalysts", [])[:5]:
            impact_color = (
                "#dc2626"
                if catalyst.get("impact") == "high"
                else "#ea580c"
                if catalyst.get("impact") == "medium"
                else "#d97706"
            )
            sentiment_icon = (
                "📈"
                if catalyst.get("sentiment") == "positive"
                else "📉"
                if catalyst.get("sentiment") == "negative"
                else "➡️"
            )

            source_html = ""
            if catalyst.get("source_url"):
                source_name = catalyst.get("source_name", "Read more")
                source_html = f"""
                <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #d1d5db;">
                    <a href="{catalyst.get('source_url')}" style="font-size: 11px; color: #2563eb; text-decoration: none; font-weight: 600;">
                        🔗 {source_name} →
                    </a>
                </div>
                """

            catalysts_html += f"""
            <div style="background-color: #f9fafb; padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 3px solid {impact_color};">
                <div style="display: flex; justify-content: between; margin-bottom: 6px;">
                    <span style="font-size: 12px; color: {impact_color}; font-weight: bold; text-transform: uppercase;">
                        {catalyst.get('impact', 'medium')} IMPACT {sentiment_icon}
                    </span>
                </div>
                <h4 style="margin: 0 0 6px 0; font-size: 14px; color: #111827; font-weight: 600;">
                    {catalyst.get('title', 'Event to Watch')}
                </h4>
                <p style="margin: 0; font-size: 12px; color: #4b5563;">
                    {catalyst.get('summary', '')}
                </p>
                {source_html}
            </div>
            """

        # Holdings impact HTML (potential impact)
        holdings_html = ""
        for holding in holdings_impact[:10]:
            impact_colors = {"positive": "#059669", "negative": "#dc2626", "neutral": "#6b7280"}
            impact_color = impact_colors.get(holding.get("impact", "neutral").lower(), "#6b7280")
            impact_icon = (
                "📈"
                if holding.get("impact") == "positive"
                else "📉"
                if holding.get("impact") == "negative"
                else "➡️"
            )

            holdings_html += f"""
            <div style="background-color: #f9fafb; padding: 12px; border-radius: 8px; margin-bottom: 8px; border-left: 3px solid {impact_color};">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <h4 style="margin: 0; font-size: 16px; color: #111827; font-weight: 700;">{holding.get('ticker', 'N/A')}</h4>
                    <span style="font-size: 12px; color: {impact_color}; font-weight: bold;">
                        {impact_icon} {holding.get('impact', 'neutral').upper()}
                    </span>
                </div>
                <p style="margin: 0; font-size: 12px; color: #4b5563;">
                    {holding.get('explanation', 'No explanation available')}
                </p>
            </div>
            """

        return f"""
        <html>
        <head>
            <meta name="color-scheme" content="light dark">
            <meta name="supported-color-schemes" content="light dark">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f5f5f5; color: #1a1a1a; padding: 20px; line-height: 1.6;">
            <div style="max-width: 750px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; padding: 28px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">

                <!-- Header -->
                <h1 style="color: #2563eb; margin: 0 0 6px 0; font-size: 26px; font-weight: 700;">🌅 Market Preview - Good Morning!</h1>
                <p style="color: #6b7280; font-size: 13px; margin: 0 0 24px 0;">{current_time}</p>

                <!-- Market Outlook Card -->
                <div style="background: {sentiment_bg}; border: 2px solid {sentiment_color}; border-radius: 10px; padding: 20px; margin-bottom: 24px;">
                    <div style="text-align: center;">
                        <h2 style="margin: 0 0 8px 0; font-size: 22px; color: {sentiment_color}; font-weight: 700;">
                            TODAY'S OUTLOOK: {sentiment.upper()}
                        </h2>
                        <div style="font-size: 48px; font-weight: bold; color: {sentiment_color}; margin: 8px 0;">
                            {sentiment_score}
                        </div>
                        <p style="margin: 12px 0 0 0; font-size: 14px; color: #1f2937; line-height: 1.6;">
                            {market_summary}
                        </p>
                    </div>
                </div>

                <!-- Key Events to Watch -->
                <div style="margin-bottom: 28px;">
                    <h2 style="color: #d97706; font-size: 18px; margin: 0 0 14px 0; border-bottom: 2px solid #92400e; padding-bottom: 8px;">
                        👀 What to Watch Today
                    </h2>
                    {catalysts_html}
                </div>

                <!-- Potential Portfolio Impact -->
                {f'''
                <div style="margin-bottom: 28px;">
                    <h2 style="color: #1d4ed8; font-size: 18px; margin: 0 0 14px 0; border-bottom: 2px solid #1e40af; padding-bottom: 8px;">
                        💼 Potential Impact on Your Shadow Portfolio
                    </h2>
                    {holdings_html}
                </div>
                ''' if holdings_html else ''}

                <!-- Portfolio Health -->
                {f'''
                <div style="background-color: #f9fafb; border: 1px solid #d1d5db; border-radius: 10px; padding: 18px; margin-bottom: 24px;">
                    <h2 style="color: #1e40af; margin: 0 0 14px 0; font-size: 18px; font-weight: 700;">📊 Portfolio Snapshot</h2>
                    <div style="display: grid; gap: 12px;">
                        <div style="display: flex; justify-content: space-between;">
                            <span style="font-size: 13px; color: #4b5563;">Total Positions:</span>
                            <span style="font-size: 15px; font-weight: bold;">{portfolio_health.get('total_positions', 0)}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between;">
                            <span style="font-size: 13px; color: #4b5563;">Risk Score:</span>
                            <span style="font-size: 15px; font-weight: bold; color: {'#059669' if portfolio_health.get('risk_score', 5) < 4 else '#d97706' if portfolio_health.get('risk_score', 5) < 7 else '#dc2626'};">
                                {portfolio_health.get('risk_score', 5.0)}/10
                            </span>
                        </div>
                    </div>
                </div>
                ''' if portfolio_health and portfolio_health.get('total_positions') is not None else ''}

                <!-- Footer -->
                <div style="margin-top: 32px; padding-top: 20px; border-top: 1px solid #d1d5db; text-align: center;">
                    <p style="color: #6b7280; font-size: 12px; margin: 0 0 6px 0;">
                        Powered by Silicon Oracle AI | Market Preview (9 AM)
                    </p>
                    <p style="color: #6b7280; font-size: 11px; margin: 0;">
                        ⚠️ This is AI-generated guidance. Always do your own research.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
