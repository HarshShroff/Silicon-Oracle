"""
Silicon Oracle - News Monitoring Service
Monitors news for holdings and identifies important/breaking news
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class NewsMonitor:
    """
    Monitors news for portfolio holdings.
    Identifies breaking news, earnings-related news, and significant events.
    """

    # Keywords that indicate important news
    IMPORTANT_KEYWORDS = [
        # Earnings & Financial
        "earnings",
        "revenue",
        "profit",
        "loss",
        "guidance",
        "forecast",
        "beat",
        "miss",
        "eps",
        "quarterly",
        "annual report",
        # Market Moving
        "surge",
        "plunge",
        "soar",
        "crash",
        "rally",
        "tumble",
        "spike",
        "record high",
        "all-time",
        "breaking",
        # Corporate Actions
        "merger",
        "acquisition",
        "buyout",
        "ipo",
        "spinoff",
        "dividend",
        "stock split",
        "buyback",
        "restructuring",
        # Regulatory & Legal
        "sec",
        "fda",
        "approved",
        "rejected",
        "lawsuit",
        "investigation",
        "regulatory",
        "compliance",
        # Leadership
        "ceo",
        "cfo",
        "resign",
        "appointed",
        "executive",
        # Analyst Actions
        "upgrade",
        "downgrade",
        "price target",
        "rating",
        "analyst",
        # Other Significant
        "contract",
        "partnership",
        "deal",
        "launch",
        "expansion",
    ]

    # Sentiment indicators
    POSITIVE_WORDS = [
        "surge",
        "soar",
        "rally",
        "beat",
        "exceed",
        "upgrade",
        "approved",
        "growth",
        "profit",
        "gain",
        "record",
        "breakthrough",
        "success",
    ]

    NEGATIVE_WORDS = [
        "plunge",
        "crash",
        "tumble",
        "miss",
        "downgrade",
        "rejected",
        "loss",
        "decline",
        "lawsuit",
        "investigation",
        "warning",
        "concern",
    ]

    def __init__(self, stock_service=None):
        self.stock_service = stock_service

    def get_news_for_holdings(
        self, tickers: List[str], limit_per_ticker: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Fetch news for multiple tickers and aggregate.
        Returns sorted by publish date (most recent first).
        """
        if not self.stock_service:
            from flask_app.services.stock_service import StockService

            self.stock_service = StockService()

        all_news = []

        for ticker in tickers:
            try:
                news = self.stock_service.get_news(ticker, limit=limit_per_ticker)
                for item in news:
                    item["ticker"] = ticker
                    item["importance"] = self._calculate_importance(item)
                    item["sentiment"] = self._analyze_sentiment(item)
                    all_news.append(item)
            except Exception as e:
                logger.warning(f"Failed to fetch news for {ticker}: {e}")

        # Sort by importance and recency
        all_news.sort(key=lambda x: (x.get("importance", 0), x.get("published", "")), reverse=True)

        return all_news

    def get_breaking_news(self, tickers: List[str], hours_back: int = 24) -> List[Dict[str, Any]]:
        """
        Get breaking/important news from the last N hours.
        """
        all_news = self.get_news_for_holdings(tickers, limit_per_ticker=10)

        # Filter for high importance and recent
        breaking = []
        cutoff = datetime.now() - timedelta(hours=hours_back)

        for item in all_news:
            if item.get("importance", 0) >= 7:  # High importance threshold
                # Try to parse published date
                if self._is_recent(item.get("published", ""), cutoff):
                    breaking.append(item)

        return breaking[:10]  # Return top 10 breaking news

    def check_for_alerts(
        self, tickers: List[str], last_check: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Check for news that should trigger alerts.
        Returns list of news items that warrant user notification.
        """
        if last_check is None:
            last_check = datetime.now() - timedelta(hours=1)

        all_news = self.get_news_for_holdings(tickers, limit_per_ticker=5)

        alert_worthy = []
        for item in all_news:
            # Check if news is recent and important enough
            if item.get("importance", 0) >= 8:  # Very important
                if self._is_recent(item.get("published", ""), last_check):
                    alert_worthy.append(
                        {
                            "type": "NEWS_ALERT",
                            "ticker": item.get("ticker"),
                            "priority": "HIGH" if item.get("importance", 0) >= 9 else "MEDIUM",
                            "message": item.get("headline", "Breaking news"),
                            "sentiment": item.get("sentiment", "neutral"),
                            "url": item.get("url"),
                            "source": item.get("source"),
                        }
                    )

        return alert_worthy

    def _calculate_importance(self, news_item: Dict[str, Any]) -> int:
        """
        Calculate importance score (1-10) based on keywords and patterns.
        """
        headline = (news_item.get("headline", "") or "").lower()
        score: float = 5  # Base score

        # Check for important keywords
        keyword_matches = sum(1 for kw in self.IMPORTANT_KEYWORDS if kw in headline)
        score += min(keyword_matches * 1.5, 4)  # Up to +4 for keywords

        # Boost for specific high-impact terms
        if any(term in headline for term in ["earnings", "beat", "miss", "guidance"]):
            score += 1
        if any(term in headline for term in ["merger", "acquisition", "buyout"]):
            score += 1.5
        if any(term in headline for term in ["fda", "approved", "rejected"]):
            score += 2
        if "breaking" in headline:
            score += 1

        # Cap at 10
        return min(int(score), 10)

    def _analyze_sentiment(self, news_item: Dict[str, Any]) -> str:
        """
        Analyze sentiment of news headline.
        Returns: 'positive', 'negative', or 'neutral'
        """
        headline = (news_item.get("headline", "") or "").lower()

        positive_count = sum(1 for word in self.POSITIVE_WORDS if word in headline)
        negative_count = sum(1 for word in self.NEGATIVE_WORDS if word in headline)

        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        return "neutral"

    def _is_recent(self, published_str: str, cutoff: datetime) -> bool:
        """
        Check if a news item is more recent than the cutoff time.
        """
        if not published_str:
            return True  # Assume recent if no date

        try:
            # Try common date formats
            formats = [
                "%a, %d %b %Y %H:%M:%S %Z",
                "%a, %d %b %Y %H:%M:%S %z",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ]

            for fmt in formats:
                try:
                    published = datetime.strptime(published_str, fmt)
                    # Handle timezone-naive comparison
                    if published.tzinfo:
                        published = published.replace(tzinfo=None)
                    return published >= cutoff
                except ValueError:
                    continue

            # If parsing fails, check for relative time strings
            if "hour" in published_str.lower() or "minute" in published_str.lower():
                return True
            if "day" in published_str.lower():
                # Extract number of days
                match = re.search(r"(\d+)\s*day", published_str.lower())
                if match:
                    days = int(match.group(1))
                    return days <= 1

            return True  # Default to recent if can't parse

        except Exception:
            return True  # Default to recent if error


class NewsAlertTracker:
    """
    Tracks which news items have already been sent as alerts
    to avoid duplicate notifications.
    """

    def __init__(self):
        self._sent_alerts = {}  # ticker -> set of headline hashes

    def is_new_alert(self, ticker: str, headline: str) -> bool:
        """Check if this news has already been alerted."""
        headline_hash = hash(headline.lower().strip())
        ticker_alerts = self._sent_alerts.get(ticker, set())
        return headline_hash not in ticker_alerts

    def mark_as_sent(self, ticker: str, headline: str):
        """Mark a news item as already alerted."""
        headline_hash = hash(headline.lower().strip())
        if ticker not in self._sent_alerts:
            self._sent_alerts[ticker] = set()
        self._sent_alerts[ticker].add(headline_hash)

    def cleanup_old_alerts(self, max_per_ticker: int = 100):
        """Clean up old alert tracking to prevent memory growth."""
        for ticker in self._sent_alerts:
            if len(self._sent_alerts[ticker]) > max_per_ticker:
                # Keep only the most recent half
                alerts = list(self._sent_alerts[ticker])
                self._sent_alerts[ticker] = set(alerts[max_per_ticker // 2 :])
