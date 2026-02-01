"""
Silicon Oracle - AI-Powered Market Intelligence Service
Scans broad financial/geopolitical news and generates personalized stock recommendations.
Uses Google Gemini AI with search grounding for comprehensive market analysis.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from flask_app.services.stock_service import StockService
from flask_app.services.oracle_service import OracleService
from flask_app.services.gemini_service import GeminiService
from flask_app.services.email_service import EmailService

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

    def __init__(self, config: Dict[str, str] = None):
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
        hours_back: int = 1
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

            # Step 1: Get AI-powered market analysis
            market_analysis = self._get_comprehensive_market_analysis()

            if not market_analysis or not market_analysis.get('has_important_news'):
                logger.info(f"No significant market developments for {user_email}")
                return False

            # Step 2: Generate personalized stock recommendations
            recommendations = self._generate_personalized_recommendations(
                market_analysis=market_analysis,
                user_holdings=user_holdings,
                risk_profile=risk_profile,
                available_cash=available_cash
            )

            if not recommendations:
                logger.info(f"No actionable recommendations for {user_email}")
                return False

            # Step 3: Analyze current holdings impact
            holdings_impact = self._analyze_holdings_impact(
                user_holdings=user_holdings,
                market_analysis=market_analysis
            )

            # Step 4: Send comprehensive intelligence email
            return self._send_intelligence_email(
                user_email=user_email,
                market_analysis=market_analysis,
                recommendations=recommendations,
                holdings_impact=holdings_impact,
                risk_profile=risk_profile
            )

        except Exception as e:
            logger.error(f"Market intelligence generation failed: {e}", exc_info=True)
            return False

    def _get_comprehensive_market_analysis(self) -> Dict[str, Any]:
        """
        Use Gemini AI with Google Search to analyze current market conditions.
        Returns comprehensive analysis of financial, geopolitical, and sector trends.
        """
        if not self.gemini_service.client:
            logger.warning("Gemini API not configured")
            return {'has_important_news': False}

        try:
            from google.genai import types

            current_date = datetime.now().strftime("%B %d, %Y")
            current_time = datetime.now().strftime("%I:%M %p")

            # Define Google Search tool for real-time news
            google_search_tool = types.Tool(
                google_search=types.GoogleSearch()
            )

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
      "summary": "2-3 sentence explanation"
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
"""

            # Generate content with search grounding
            response = self.gemini_service.client.models.generate_content(
                model=self.gemini_service.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[google_search_tool],
                    response_modalities=["TEXT"],
                    temperature=0.3,  # Lower temperature for more factual analysis
                )
            )

            # Parse JSON response
            import json
            import re

            response_text = response.text.strip()

            # Extract JSON from response (in case there's markdown)
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
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
            return {'has_important_news': False}

    def _generate_personalized_recommendations(
        self,
        market_analysis: Dict[str, Any],
        user_holdings: List[str],
        risk_profile: str,
        available_cash: float
    ) -> List[Dict[str, Any]]:
        """
        Use AI to generate personalized stock recommendations based on:
        - Market analysis and catalysts
        - User's risk profile
        - Current holdings
        - Available cash
        """
        if not self.gemini_service.client:
            return []

        try:
            from google.genai import types

            # Build context about user
            holdings_str = ", ".join(user_holdings) if user_holdings else "None (all cash)"

            risk_descriptions = {
                "aggressive": "high-risk, high-reward growth stocks with volatility",
                "moderate": "balanced mix of growth and value with moderate risk",
                "conservative": "low-risk, stable companies with dividends and minimal volatility"
            }
            risk_desc = risk_descriptions.get(risk_profile.lower(), risk_descriptions["moderate"])

            prompt = f"""
You are a financial advisor. Based on the following market analysis, generate personalized stock recommendations.

MARKET ANALYSIS:
{json.dumps(market_analysis, indent=2)}

USER PROFILE:
- Risk Profile: {risk_profile.upper()} ({risk_desc})
- Current Holdings: {holdings_str}
- Available Cash: ${available_cash:,.2f}

Generate 5-10 specific stock recommendations (ticker symbols) with detailed reasoning.
Consider the market catalysts, sector outlook, and user's risk profile.

Return ONLY valid JSON in this format:

{{
  "recommendations": [
    {{
      "ticker": "TICKER",
      "action": "BUY|HOLD|SELL",
      "priority": "high|medium|low",
      "reasoning": "2-3 sentence explanation tied to market catalysts",
      "catalyst": "Which market catalyst drives this recommendation",
      "target_allocation": "percentage of available cash (for BUY only)",
      "risk_level": "high|medium|low",
      "timeframe": "short-term|medium-term|long-term"
    }}
  ]
}}

RULES:
1. For BUY recommendations: Only suggest tickers NOT in user's holdings
2. For HOLD recommendations: Only suggest tickers IN user's holdings that should be kept
3. For SELL recommendations: Only suggest tickers IN user's holdings that should be sold
4. Match risk_level to user's risk profile preference
5. Ensure target_allocation percentages are realistic (5-20% per position)
6. Tie each recommendation to specific catalysts from the market analysis
7. Include mix of BUY, HOLD, SELL based on holdings and market conditions
8. Return ONLY valid JSON, no markdown, no code blocks
"""

            response = self.gemini_service.client.models.generate_content(
                model=self.gemini_service.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.4,  # Slightly higher for creative recommendations
                )
            )

            # Parse JSON response
            import json
            import re

            response_text = response.text.strip()
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)

            recommendations_data = json.loads(response_text)
            recommendations = recommendations_data.get('recommendations', [])

            # Enrich with Oracle scores
            enriched = []
            for rec in recommendations:
                ticker = rec.get('ticker', '').upper()
                if not ticker:
                    continue

                try:
                    # Get Oracle score for this ticker
                    oracle_data = self.oracle_service.calculate_oracle_score(ticker)

                    enriched.append({
                        **rec,
                        'oracle_score': oracle_data.get('score', 0),
                        'oracle_max': oracle_data.get('max_score', 12),
                        'oracle_verdict': oracle_data.get('verdict_text', 'HOLD'),
                        'oracle_confidence': oracle_data.get('confidence', 0)
                    })
                except Exception as e:
                    logger.warning(f"Failed to get Oracle score for {ticker}: {e}")
                    enriched.append({**rec, 'oracle_score': None})

            logger.info(f"Generated {len(enriched)} personalized recommendations")
            return enriched

        except Exception as e:
            logger.error(f"Recommendation generation failed: {e}", exc_info=True)
            return []

    def _analyze_holdings_impact(
        self,
        user_holdings: List[str],
        market_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Analyze how current market conditions affect user's holdings.
        """
        if not user_holdings or not self.gemini_service.client:
            return []

        try:
            from google.genai import types

            holdings_str = ", ".join(user_holdings)

            prompt = f"""
Based on this market analysis:
{json.dumps(market_analysis, indent=2)}

Analyze the impact on these holdings: {holdings_str}

For each ticker, return JSON:

{{
  "holdings_impact": [
    {{
      "ticker": "TICKER",
      "impact": "positive|negative|neutral",
      "severity": "high|medium|low",
      "explanation": "2-3 sentences on how market conditions affect this stock",
      "recommendation": "hold|reduce|add|sell"
    }}
  ]
}}

Return ONLY valid JSON, no markdown.
"""

            response = self.gemini_service.client.models.generate_content(
                model=self.gemini_service.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.3)
            )

            import json
            import re

            response_text = response.text.strip()
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)

            impact_data = json.loads(response_text)
            return impact_data.get('holdings_impact', [])

        except Exception as e:
            logger.error(f"Holdings impact analysis failed: {e}", exc_info=True)
            return []

    def _send_intelligence_email(
        self,
        user_email: str,
        market_analysis: Dict[str, Any],
        recommendations: List[Dict[str, Any]],
        holdings_impact: List[Dict[str, Any]],
        risk_profile: str
    ) -> bool:
        """Send comprehensive market intelligence email with recommendations."""

        import json

        # Build subject line
        sentiment = market_analysis.get('market_sentiment', 'neutral').upper()
        sentiment_emoji = '📈' if sentiment == 'BULLISH' else '📉' if sentiment == 'BEARISH' else '➡️'

        buy_count = len([r for r in recommendations if r.get('action') == 'BUY'])
        sell_count = len([r for r in recommendations if r.get('action') == 'SELL'])

        subject = f"{sentiment_emoji} Market Intel: {buy_count} BUY, {sell_count} SELL - {sentiment} Market"

        # Build HTML email
        html_body = self._build_intelligence_email_html(
            market_analysis=market_analysis,
            recommendations=recommendations,
            holdings_impact=holdings_impact,
            risk_profile=risk_profile
        )

        # Build text email
        text_body = self._build_intelligence_email_text(
            market_analysis=market_analysis,
            recommendations=recommendations,
            holdings_impact=holdings_impact
        )

        # Send email
        success = self.email_service.send_email(
            to_email=user_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body
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
        risk_profile: str
    ) -> str:
        """Build HTML email for market intelligence."""

        current_time = datetime.now().strftime('%B %d, %Y at %I:%M %p')

        sentiment = market_analysis.get('market_sentiment', 'neutral')
        sentiment_score = market_analysis.get('sentiment_score', 50)
        market_summary = market_analysis.get('market_summary', 'No summary available')

        sentiment_colors = {
            'bullish': '#22c55e',
            'neutral': '#eab308',
            'bearish': '#ef4444'
        }
        sentiment_color = sentiment_colors.get(sentiment.lower(), '#eab308')

        # Market overview section
        catalysts_html = ""
        for catalyst in market_analysis.get('top_catalysts', [])[:5]:
            impact_color = '#ef4444' if catalyst.get('impact') == 'high' else '#f97316' if catalyst.get('impact') == 'medium' else '#eab308'
            sentiment_icon = '📈' if catalyst.get('sentiment') == 'positive' else '📉' if catalyst.get('sentiment') == 'negative' else '➡️'

            catalysts_html += f"""
            <div style="background-color: #334155; padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 3px solid {impact_color};">
                <div style="display: flex; justify-content: between; margin-bottom: 6px;">
                    <span style="font-size: 12px; color: {impact_color}; font-weight: bold; text-transform: uppercase;">
                        {catalyst.get('impact', 'medium')} IMPACT {sentiment_icon}
                    </span>
                    <span style="font-size: 11px; color: #64748b;">
                        {catalyst.get('category', 'market').upper()}
                    </span>
                </div>
                <h4 style="margin: 0 0 6px 0; font-size: 14px; color: white;">
                    {catalyst.get('title', 'Market Event')}
                </h4>
                <p style="margin: 0; font-size: 12px; color: #94a3b8;">
                    {catalyst.get('summary', '')}
                </p>
                <p style="margin: 6px 0 0 0; font-size: 11px; color: #6366f1;">
                    Sectors: {', '.join(catalyst.get('affected_sectors', []))}
                </p>
            </div>
            """

        # Recommendations section (grouped by action)
        buy_recs = [r for r in recommendations if r.get('action') == 'BUY']
        hold_recs = [r for r in recommendations if r.get('action') == 'HOLD']
        sell_recs = [r for r in recommendations if r.get('action') == 'SELL']

        def build_rec_card(rec, action_color):
            oracle_html = ""
            if rec.get('oracle_score') is not None:
                score = rec['oracle_score']
                max_score = rec.get('oracle_max', 12)
                score_pct = (score / max_score * 100) if max_score > 0 else 0
                oracle_html = f"""
                <div style="margin-top: 8px; padding: 8px; background-color: #1e293b; border-radius: 4px;">
                    <span style="font-size: 11px; color: #64748b;">Oracle: </span>
                    <span style="font-size: 13px; font-weight: bold; color: {'#22c55e' if score_pct >= 70 else '#eab308' if score_pct >= 50 else '#ef4444'};">
                        {score:.1f}/{max_score} ({score_pct:.0f}%) - {rec.get('oracle_verdict', 'N/A')}
                    </span>
                </div>
                """

            priority_colors = {'high': '#ef4444', 'medium': '#f97316', 'low': '#eab308'}
            priority_color = priority_colors.get(rec.get('priority', 'medium').lower(), '#f97316')

            return f"""
            <div style="background-color: #334155; padding: 14px; border-radius: 8px; margin-bottom: 10px; border-left: 4px solid {action_color};">
                <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
                    <h4 style="margin: 0; font-size: 18px; color: white;">
                        {rec.get('ticker', 'N/A')}
                    </h4>
                    <div style="text-align: right;">
                        <span style="background-color: {priority_color}20; color: {priority_color}; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold;">
                            {rec.get('priority', 'medium').upper()}
                        </span>
                        <div style="font-size: 11px; color: #64748b; margin-top: 4px;">
                            Risk: {rec.get('risk_level', 'medium').upper()}
                        </div>
                    </div>
                </div>
                <p style="margin: 0 0 8px 0; font-size: 13px; color: #94a3b8;">
                    {rec.get('reasoning', 'No reasoning provided')}
                </p>
                <div style="display: flex; justify-content: space-between; font-size: 11px; color: #6366f1;">
                    <span>💡 {rec.get('catalyst', 'Market conditions')}</span>
                    <span>⏱️ {rec.get('timeframe', 'medium-term')}</span>
                </div>
                {oracle_html}
            </div>
            """

        buy_html = "".join([build_rec_card(r, '#22c55e') for r in buy_recs[:5]])
        sell_html = "".join([build_rec_card(r, '#ef4444') for r in sell_recs[:5]])
        hold_html = "".join([build_rec_card(r, '#eab308') for r in hold_recs[:5]])

        # Holdings impact section
        holdings_html = ""
        for holding in holdings_impact[:10]:
            impact_colors = {'positive': '#22c55e', 'negative': '#ef4444', 'neutral': '#64748b'}
            impact_color = impact_colors.get(holding.get('impact', 'neutral').lower(), '#64748b')
            impact_icon = '📈' if holding.get('impact') == 'positive' else '📉' if holding.get('impact') == 'negative' else '➡️'

            holdings_html += f"""
            <div style="background-color: #334155; padding: 12px; border-radius: 8px; margin-bottom: 8px; border-left: 3px solid {impact_color};">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <h4 style="margin: 0; font-size: 16px; color: white;">{holding.get('ticker', 'N/A')}</h4>
                    <span style="font-size: 12px; color: {impact_color}; font-weight: bold;">
                        {impact_icon} {holding.get('impact', 'neutral').upper()} ({holding.get('severity', 'medium')})
                    </span>
                </div>
                <p style="margin: 0 0 6px 0; font-size: 12px; color: #94a3b8;">
                    {holding.get('explanation', 'No explanation available')}
                </p>
                <div style="background-color: #1e293b; padding: 6px 10px; border-radius: 4px;">
                    <span style="font-size: 11px; color: #6366f1; font-weight: bold;">
                        Recommendation: {holding.get('recommendation', 'hold').upper()}
                    </span>
                </div>
            </div>
            """

        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #0f172a; color: #e2e8f0; padding: 20px;">
            <div style="max-width: 750px; margin: 0 auto; background-color: #1e293b; border-radius: 12px; padding: 28px;">

                <!-- Header -->
                <h1 style="color: #6366f1; margin: 0 0 6px 0; font-size: 26px;">🤖 AI Market Intelligence</h1>
                <p style="color: #64748b; font-size: 13px; margin: 0 0 8px 0;">{current_time}</p>
                <p style="color: #94a3b8; font-size: 12px; margin: 0 0 24px 0;">
                    Personalized for: <span style="color: #6366f1; font-weight: bold;">{risk_profile.upper()}</span> risk profile
                </p>

                <!-- Market Sentiment Card -->
                <div style="background: linear-gradient(135deg, {sentiment_color}20, {sentiment_color}10); border: 2px solid {sentiment_color}; border-radius: 10px; padding: 20px; margin-bottom: 24px;">
                    <div style="text-align: center;">
                        <h2 style="margin: 0 0 8px 0; font-size: 22px; color: {sentiment_color};">
                            {sentiment.upper()} MARKET
                        </h2>
                        <div style="font-size: 48px; font-weight: bold; color: {sentiment_color}; margin: 8px 0;">
                            {sentiment_score}
                        </div>
                        <p style="margin: 12px 0 0 0; font-size: 14px; color: #e2e8f0; line-height: 1.6;">
                            {market_summary}
                        </p>
                    </div>
                </div>

                <!-- Key Market Catalysts -->
                <div style="margin-bottom: 28px;">
                    <h2 style="color: #fbbf24; font-size: 18px; margin: 0 0 14px 0; border-bottom: 2px solid #78350f; padding-bottom: 8px;">
                        🌍 Key Market Catalysts
                    </h2>
                    {catalysts_html}
                </div>

                <!-- BUY Recommendations -->
                {f'''
                <div style="margin-bottom: 28px;">
                    <h2 style="color: #22c55e; font-size: 18px; margin: 0 0 14px 0; border-bottom: 2px solid #065f46; padding-bottom: 8px;">
                        💰 BUY Recommendations ({len(buy_recs)})
                    </h2>
                    {buy_html}
                </div>
                ''' if buy_recs else ''}

                <!-- SELL Recommendations -->
                {f'''
                <div style="margin-bottom: 28px;">
                    <h2 style="color: #ef4444; font-size: 18px; margin: 0 0 14px 0; border-bottom: 2px solid #7f1d1d; padding-bottom: 8px;">
                        📤 SELL Recommendations ({len(sell_recs)})
                    </h2>
                    {sell_html}
                </div>
                ''' if sell_recs else ''}

                <!-- HOLD Recommendations -->
                {f'''
                <div style="margin-bottom: 28px;">
                    <h2 style="color: #eab308; font-size: 18px; margin: 0 0 14px 0; border-bottom: 2px solid #78350f; padding-bottom: 8px;">
                        🤝 HOLD Recommendations ({len(hold_recs)})
                    </h2>
                    {hold_html}
                </div>
                ''' if hold_recs else ''}

                <!-- Holdings Impact -->
                {f'''
                <div style="margin-bottom: 28px;">
                    <h2 style="color: #93c5fd; font-size: 18px; margin: 0 0 14px 0; border-bottom: 2px solid #1e3a8a; padding-bottom: 8px;">
                        📊 Your Holdings Impact Analysis
                    </h2>
                    {holdings_html}
                </div>
                ''' if holdings_html else ''}

                <!-- Footer -->
                <div style="margin-top: 32px; padding-top: 20px; border-top: 1px solid #334155; text-align: center;">
                    <p style="color: #64748b; font-size: 12px; margin: 0 0 6px 0;">
                        Powered by Silicon Oracle AI | Google Gemini + Oracle 15-Factor Analysis
                    </p>
                    <p style="color: #64748b; font-size: 11px; margin: 0;">
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
        holdings_impact: List[Dict[str, Any]]
    ) -> str:
        """Build plain text email."""

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
        for idx, catalyst in enumerate(market_analysis.get('top_catalysts', [])[:5], 1):
            text += f"\n{idx}. [{catalyst.get('impact', 'medium').upper()}] {catalyst.get('title', 'Event')}\n"
            text += f"   {catalyst.get('summary', '')}\n"
            text += f"   Sectors: {', '.join(catalyst.get('affected_sectors', []))}\n"

        # BUY recommendations
        buy_recs = [r for r in recommendations if r.get('action') == 'BUY']
        if buy_recs:
            text += f"\n\n{'=' * 70}\nBUY RECOMMENDATIONS ({len(buy_recs)})\n{'=' * 70}\n"
            for idx, rec in enumerate(buy_recs, 1):
                text += f"\n{idx}. {rec.get('ticker', 'N/A')} - {rec.get('priority', 'medium').upper()} PRIORITY\n"
                text += f"   {rec.get('reasoning', '')}\n"
                if rec.get('oracle_score'):
                    text += f"   Oracle: {rec['oracle_score']:.1f}/{rec.get('oracle_max', 12)} - {rec.get('oracle_verdict', 'N/A')}\n"

        # SELL recommendations
        sell_recs = [r for r in recommendations if r.get('action') == 'SELL']
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
