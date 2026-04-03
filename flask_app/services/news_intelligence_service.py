"""
Silicon Oracle - News Intelligence Service
Hourly news scanning with AI-powered analysis and Oracle verdicts.
Sends comprehensive email alerts only when important news is detected.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from flask_app.services.email_service import EmailService
from flask_app.services.gemini_service import GeminiService
from flask_app.services.news_monitor import NewsMonitor
from flask_app.services.oracle_service import OracleService
from flask_app.services.stock_service import StockService

logger = logging.getLogger(__name__)


class NewsIntelligenceService:
    """
    Comprehensive news intelligence system that:
    1. Scans news for portfolio holdings + major market indices
    2. Analyzes importance and filters for actionable news
    3. Gets AI analysis and Oracle verdicts for affected stocks
    4. Sends detailed email digest only if important news found
    """

    # Major market tickers to monitor (in addition to user holdings)
    MARKET_INDICES = ["SPY", "QQQ", "DIA", "IWM"]  # S&P 500, Nasdaq, Dow, Russell 2000

    # Top stocks to monitor for broader market sentiment
    MAJOR_STOCKS = [
        "AAPL",
        "MSFT",
        "GOOGL",
        "AMZN",
        "NVDA",  # Tech giants
        "TSLA",
        "META",
        "JPM",
        "V",
        "WMT",  # Other major players
    ]

    # Minimum importance score to include in digest (0-10)
    IMPORTANCE_THRESHOLD = 7

    def __init__(self, config: Optional[Dict[str, str]] = None):
        self.config = config or {}
        self.stock_service = StockService(config)
        self.oracle_service = OracleService(config)
        self.gemini_service = GeminiService(config)
        self.news_monitor = NewsMonitor(self.stock_service)
        self.email_service = EmailService(config)

    def scan_and_notify(
        self,
        user_holdings: List[str],
        user_email: str,
        include_market_news: bool = True,
        hours_back: int = 1,
    ) -> bool:
        """
        Main entry point: Scan news and send email if important news found.

        Args:
            user_holdings: List of ticker symbols in user's portfolio
            user_email: Email address to send alerts to
            include_market_news: Whether to include major market/stock news
            hours_back: How many hours of news to scan

        Returns:
            True if email was sent, False if no important news or error
        """
        try:
            logger.info(f"Starting news intelligence scan for {user_email}")
            logger.info(f"Scanning {len(user_holdings)} holdings + market news")

            # Build complete ticker list
            tickers_to_scan = list(set(user_holdings))  # Remove duplicates

            if include_market_news:
                tickers_to_scan.extend(self.MARKET_INDICES)
                tickers_to_scan.extend(self.MAJOR_STOCKS)
                tickers_to_scan = list(set(tickers_to_scan))  # Remove duplicates

            # Fetch all news
            all_news = self.news_monitor.get_news_for_holdings(
                tickers=tickers_to_scan, limit_per_ticker=10
            )

            if not all_news:
                logger.info("No news found in scan")
                return False

            # Filter for recent and important news
            important_news = self._filter_important_news(
                all_news, hours_back=hours_back, threshold=self.IMPORTANCE_THRESHOLD
            )

            if not important_news:
                logger.info(f"No important news above threshold {self.IMPORTANCE_THRESHOLD}")
                return False

            logger.info(f"Found {len(important_news)} important news items")

            # Analyze each important news item with AI and Oracle
            analyzed_news = self._analyze_news_items(important_news, user_holdings)

            if not analyzed_news:
                logger.info("No news passed analysis filters")
                return False

            # Group news by ticker
            news_by_ticker = self._group_news_by_ticker(analyzed_news)

            # Send comprehensive email
            return self._send_comprehensive_email(
                user_email=user_email, news_by_ticker=news_by_ticker, user_holdings=user_holdings
            )

        except Exception as e:
            logger.error(f"News intelligence scan failed: {e}", exc_info=True)
            return False

    def _filter_important_news(
        self, news_items: List[Dict[str, Any]], hours_back: int, threshold: int
    ) -> List[Dict[str, Any]]:
        """Filter news for recency and importance."""
        cutoff = datetime.now() - timedelta(hours=hours_back)
        important = []

        for item in news_items:
            # Check importance score
            if item.get("importance", 0) < threshold:
                continue

            # Check recency
            if not self.news_monitor._is_recent(item.get("published", ""), cutoff):
                continue

            important.append(item)

        # Sort by importance (highest first)
        important.sort(key=lambda x: x.get("importance", 0), reverse=True)

        # Limit to top 20 most important to avoid overwhelming
        return important[:20]

    def _analyze_news_items(
        self, news_items: List[Dict[str, Any]], user_holdings: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Analyze each news item with AI insights and Oracle verdict.
        Only include news with actionable intelligence.
        """
        analyzed = []

        for item in news_items:
            ticker = item.get("ticker", "")

            try:
                # Get Oracle verdict for this stock
                oracle_data = self.oracle_service.calculate_oracle_score(ticker)

                # Get AI analysis if Gemini is configured
                ai_insight = None
                if self.gemini_service.client:
                    ai_insight = self.gemini_service.get_quick_insight(ticker)

                # Determine if this is a user holding
                is_holding = ticker in user_holdings

                # Build enriched news item
                enriched = {
                    **item,  # Original news data
                    "oracle_score": oracle_data.get("score", 0),
                    "oracle_max": oracle_data.get("max_score", 12),
                    "oracle_verdict": oracle_data.get("verdict_text", "HOLD"),
                    "oracle_confidence": oracle_data.get("confidence", 0),
                    "ai_insight": ai_insight,
                    "is_holding": is_holding,
                    "priority": self._calculate_priority(item, oracle_data, is_holding),
                }

                analyzed.append(enriched)

            except Exception as e:
                logger.warning(f"Failed to analyze news for {ticker}: {e}")
                # Include without analysis rather than skip
                analyzed.append(
                    {
                        **item,
                        "oracle_score": None,
                        "oracle_verdict": "N/A",
                        "ai_insight": None,
                        "is_holding": ticker in user_holdings,
                        "priority": "MEDIUM",
                    }
                )

        return analyzed

    def _calculate_priority(
        self, news_item: Dict[str, Any], oracle_data: Dict[str, Any], is_holding: bool
    ) -> str:
        """
        Calculate alert priority based on news importance, Oracle verdict, and holding status.
        Returns: CRITICAL, HIGH, MEDIUM, or LOW
        """
        importance = news_item.get("importance", 5)
        sentiment = news_item.get("sentiment", "neutral")
        oracle_score = oracle_data.get("score", 0)
        oracle_max = oracle_data.get("max_score", 12)
        oracle_pct = (oracle_score / oracle_max * 100) if oracle_max > 0 else 50

        # CRITICAL: Very important news for holdings with major sentiment
        if is_holding and importance >= 9 and sentiment != "neutral":
            return "CRITICAL"

        # HIGH: Important news for holdings OR very important market news
        if (is_holding and importance >= 8) or (importance >= 9):
            return "HIGH"

        # HIGH: Holdings with extreme Oracle scores and negative news
        if is_holding and (oracle_pct <= 30 or oracle_pct >= 80) and sentiment != "neutral":
            return "HIGH"

        # MEDIUM: Moderate importance or market-related
        if importance >= 7:
            return "MEDIUM"

        return "LOW"

    def _group_news_by_ticker(
        self, news_items: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group news items by ticker symbol."""
        grouped: Dict[str, List[Dict[str, Any]]] = {}

        for item in news_items:
            ticker = item.get("ticker", "OTHER")
            if ticker not in grouped:
                grouped[ticker] = []
            grouped[ticker].append(item)

        # Sort each ticker's news by priority and importance
        priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        for ticker in grouped:
            grouped[ticker].sort(
                key=lambda x: (
                    priority_order.get(x.get("priority", "LOW"), 4),
                    -x.get("importance", 0),
                )
            )

        return grouped

    def _send_comprehensive_email(
        self,
        user_email: str,
        news_by_ticker: Dict[str, List[Dict[str, Any]]],
        user_holdings: List[str],
    ) -> bool:
        """Send comprehensive news intelligence digest email."""

        # Count news items by priority
        priority_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        total_items = 0

        for ticker_news in news_by_ticker.values():
            for item in ticker_news:
                priority = item.get("priority", "LOW")
                priority_counts[priority] += 1
                total_items += 1

        # Create subject line based on priority
        if priority_counts["CRITICAL"] > 0:
            subject = (
                f"🚨 CRITICAL: {priority_counts['CRITICAL']} Major Alert(s) - Silicon Oracle News"
            )
        elif priority_counts["HIGH"] > 0:
            subject = (
                f"⚠️ HIGH Priority: {priority_counts['HIGH']} Important Alert(s) - Silicon Oracle"
            )
        else:
            subject = f"📰 Market Intelligence: {total_items} Updates - Silicon Oracle"

        # Build HTML email
        html_body = self._build_news_email_html(news_by_ticker, user_holdings, priority_counts)
        text_body = self._build_news_email_text(news_by_ticker, user_holdings)

        # Send email
        success = self.email_service.send_email(
            to_email=user_email, subject=subject, html_body=html_body, text_body=text_body
        )

        if success:
            logger.info(f"News intelligence email sent to {user_email}")
        else:
            logger.error(f"Failed to send news intelligence email to {user_email}")

        return success

    def _build_news_email_html(
        self,
        news_by_ticker: Dict[str, List[Dict[str, Any]]],
        user_holdings: List[str],
        priority_counts: Dict[str, int],
    ) -> str:
        """Build HTML email body for news digest."""

        current_time = datetime.now().strftime("%B %d, %Y at %I:%M %p")

        # Priority summary
        priority_cards = ""
        if priority_counts["CRITICAL"] > 0:
            priority_cards += f"""
            <div style="background-color: #7f1d1d; padding: 12px; border-radius: 8px; margin-bottom: 8px;">
                <span style="font-weight: bold; color: #fca5a5;">🚨 CRITICAL: {priority_counts['CRITICAL']} alert(s)</span>
            </div>
            """
        if priority_counts["HIGH"] > 0:
            priority_cards += f"""
            <div style="background-color: #78350f; padding: 12px; border-radius: 8px; margin-bottom: 8px;">
                <span style="font-weight: bold; color: #fbbf24;">⚠️ HIGH: {priority_counts['HIGH']} alert(s)</span>
            </div>
            """
        if priority_counts["MEDIUM"] > 0:
            priority_cards += f"""
            <div style="background-color: #1e3a8a; padding: 12px; border-radius: 8px; margin-bottom: 8px;">
                <span style="font-weight: bold; color: #93c5fd;">📊 MEDIUM: {priority_counts['MEDIUM']} alert(s)</span>
            </div>
            """

        # Build ticker sections (holdings first, then market)
        holdings_sections = ""
        market_sections = ""

        for ticker in sorted(news_by_ticker.keys()):
            news_items = news_by_ticker[ticker]
            is_holding = ticker in user_holdings

            section_html = self._build_ticker_section_html(ticker, news_items, is_holding)

            if is_holding:
                holdings_sections += section_html
            else:
                market_sections += section_html

        # Combine sections
        all_sections = ""
        if holdings_sections:
            all_sections += f"""
            <div style="margin: 24px 0;">
                <h2 style="color: #fbbf24; font-size: 18px; margin-bottom: 16px; border-bottom: 2px solid #78350f; padding-bottom: 8px;">
                    📊 YOUR HOLDINGS
                </h2>
                {holdings_sections}
            </div>
            """

        if market_sections:
            all_sections += f"""
            <div style="margin: 24px 0;">
                <h2 style="color: #93c5fd; font-size: 18px; margin-bottom: 16px; border-bottom: 2px solid #1e3a8a; padding-bottom: 8px;">
                    🌐 MARKET & KEY STOCKS
                </h2>
                {market_sections}
            </div>
            """

        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #0f172a; color: #e2e8f0; padding: 20px;">
            <div style="max-width: 700px; margin: 0 auto; background-color: #1e293b; border-radius: 12px; padding: 24px;">
                <h1 style="color: #6366f1; margin-bottom: 8px;">📰 News Intelligence Digest</h1>
                <p style="color: #64748b; font-size: 14px; margin-bottom: 24px;">{current_time}</p>

                <div style="margin-bottom: 24px;">
                    {priority_cards}
                </div>

                {all_sections}

                <div style="margin-top: 32px; padding-top: 24px; border-top: 1px solid #334155; text-align: center;">
                    <p style="color: #64748b; font-size: 12px; margin: 0;">
                        Powered by Silicon Oracle AI | Oracle Score + Google Gemini Analysis
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

    def _build_ticker_section_html(
        self, ticker: str, news_items: List[Dict[str, Any]], is_holding: bool
    ) -> str:
        """Build HTML section for a single ticker's news."""

        # Get first item for Oracle score (same for all items of this ticker)
        first_item = news_items[0]
        oracle_score = first_item.get("oracle_score")
        oracle_max = first_item.get("oracle_max", 12)
        oracle_verdict = first_item.get("oracle_verdict", "N/A")

        # Oracle score badge
        oracle_html = ""
        if oracle_score is not None:
            score_pct = (oracle_score / oracle_max * 100) if oracle_max > 0 else 0
            score_color = (
                "#22c55e" if score_pct >= 70 else "#eab308" if score_pct >= 50 else "#ef4444"
            )
            oracle_html = f"""
            <div style="background-color: #334155; padding: 12px; border-radius: 8px; margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <p style="margin: 0; font-size: 12px; color: #94a3b8;">Oracle Score</p>
                        <p style="margin: 4px 0 0 0; font-size: 20px; font-weight: bold; color: {score_color};">
                            {oracle_score:.1f}/{oracle_max} ({score_pct:.0f}%)
                        </p>
                    </div>
                    <div style="text-align: right;">
                        <p style="margin: 0; font-size: 12px; color: #94a3b8;">Verdict</p>
                        <p style="margin: 4px 0 0 0; font-size: 16px; font-weight: bold; color: white;">
                            {oracle_verdict}
                        </p>
                    </div>
                </div>
            </div>
            """

        # Build news items list
        news_html = ""
        for idx, item in enumerate(news_items[:5]):  # Max 5 news per ticker
            priority = item.get("priority", "MEDIUM")
            priority_colors = {
                "CRITICAL": "#ef4444",
                "HIGH": "#f97316",
                "MEDIUM": "#3b82f6",
                "LOW": "#64748b",
            }
            priority_color = priority_colors.get(priority, "#64748b")

            sentiment = item.get("sentiment", "neutral")
            sentiment_emoji = (
                "📈" if sentiment == "positive" else "📉" if sentiment == "negative" else "➡️"
            )

            ai_insight_html = ""
            if item.get("ai_insight"):
                ai_insight_html = f"""
                <p style="margin: 8px 0 0 0; font-size: 13px; color: #93c5fd; font-style: italic; padding-left: 12px; border-left: 2px solid #3b82f6;">
                    💡 {item['ai_insight']}
                </p>
                """

            news_html += f"""
            <div style="background-color: #334155; padding: 14px; border-radius: 8px; margin-bottom: 10px; border-left: 3px solid {priority_color};">
                <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 6px;">
                    <span style="background-color: {priority_color}20; color: {priority_color}; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold;">
                        {priority}
                    </span>
                    <span style="font-size: 12px; color: #64748b;">
                        {sentiment_emoji} {item.get('source', 'Unknown')}
                    </span>
                </div>
                <h4 style="margin: 0 0 8px 0; font-size: 15px; color: white; font-weight: 600;">
                    {item.get('headline', 'No headline')[:120]}{'...' if len(item.get('headline', '')) > 120 else ''}
                </h4>
                <p style="margin: 0; font-size: 12px; color: #94a3b8;">
                    Importance: {item.get('importance', 0)}/10 | {item.get('published', 'Recent')}
                </p>
                {ai_insight_html}
                <a href="{item.get('url', '#')}" style="display: inline-block; margin-top: 8px; color: #6366f1; font-size: 12px; text-decoration: none;">
                    Read Full Article →
                </a>
            </div>
            """

        holding_badge = ""
        if is_holding:
            holding_badge = "<span style='background-color: #065f46; color: #10b981; padding: 4px 8px; border-radius: 4px; font-size: 12px; margin-left: 8px;'>📊 HOLDING</span>"

        return f"""
        <div style="margin-bottom: 28px; padding: 16px; background-color: #1e293b; border-radius: 10px; border: 1px solid #334155;">
            <h3 style="color: #e2e8f0; margin: 0 0 12px 0; font-size: 20px;">
                {ticker}{holding_badge}
            </h3>
            {oracle_html}
            {news_html}
        </div>
        """

    def _build_news_email_text(
        self, news_by_ticker: Dict[str, List[Dict[str, Any]]], user_holdings: List[str]
    ) -> str:
        """Build plain text email body for news digest."""

        text = f"""
SILICON ORACLE NEWS INTELLIGENCE DIGEST
{datetime.now().strftime('%B %d, %Y at %I:%M %p')}
{'=' * 60}

"""

        # Holdings first
        holdings_text = ""
        for ticker in sorted(news_by_ticker.keys()):
            if ticker not in user_holdings:
                continue

            news_items = news_by_ticker[ticker]
            holdings_text += f"\n{'*' * 60}\n"
            holdings_text += f"📊 {ticker} (YOUR HOLDING)\n"
            holdings_text += f"{'*' * 60}\n\n"

            first_item = news_items[0]
            if first_item.get("oracle_score") is not None:
                holdings_text += f"Oracle Score: {first_item['oracle_score']:.1f}/{first_item.get('oracle_max', 12)} - {first_item.get('oracle_verdict', 'N/A')}\n\n"

            for idx, item in enumerate(news_items[:5], 1):
                holdings_text += f"{idx}. [{item.get('priority', 'MEDIUM')}] {item.get('headline', 'No headline')}\n"
                holdings_text += f"   Importance: {item.get('importance', 0)}/10 | {item.get('sentiment', 'neutral')}\n"
                if item.get("ai_insight"):
                    holdings_text += f"   💡 {item['ai_insight']}\n"
                holdings_text += f"   {item.get('url', '')}\n\n"

        if holdings_text:
            text += "\nYOUR HOLDINGS\n" + "=" * 60 + holdings_text

        # Market news
        market_text = ""
        for ticker in sorted(news_by_ticker.keys()):
            if ticker in user_holdings:
                continue

            news_items = news_by_ticker[ticker]
            market_text += f"\n{ticker}\n{'-' * 40}\n"

            for idx, item in enumerate(news_items[:3], 1):
                market_text += f"{idx}. {item.get('headline', 'No headline')[:80]}...\n"
                market_text += f"   {item.get('priority', 'MEDIUM')} | Importance: {item.get('importance', 0)}/10\n\n"

        if market_text:
            text += "\n\nMARKET & KEY STOCKS\n" + "=" * 60 + market_text

        text += "\n" + "=" * 60
        text += "\nPowered by Silicon Oracle AI"

        return text
