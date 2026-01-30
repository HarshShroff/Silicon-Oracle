"""
Hybrid Data Fetcher - Best of All APIs
Uses Finnhub, Alpaca, Alpha Vantage, and yfinance strategically
"""

import streamlit as st
import finnhub
import requests
from typing import Optional, Dict, Any, List
from datetime import datetime


class HybridDataFetcher:
    """Smart data fetcher that uses the best API for each type of data."""

    def __init__(self):
        self.finnhub_client = None
        self._initialize_finnhub()

    def _initialize_finnhub(self):
        """Initialize Finnhub client."""
        try:
            api_key = st.secrets.get("finnhub", {}).get("api_key")
            if api_key:
                self.finnhub_client = finnhub.Client(api_key=api_key)
        except Exception as e:
            st.warning(f"Finnhub initialization failed: {e}")

    def get_real_time_quote(self, ticker: str) -> Optional[Dict[str, float]]:
        """
        Get real-time quote from Finnhub (fastest, most reliable).

        Returns:
            {
                'current': float,
                'high': float,
                'low': float,
                'open': float,
                'previous_close': float,
                'change': float,
                'percent_change': float
            }
        """
        if not self.finnhub_client:
            return None

        try:
            quote = self.finnhub_client.quote(ticker)

            if quote and quote.get('c', 0) > 0:  # 'c' is current price
                return {
                    'current': quote['c'],
                    'high': quote['h'],
                    'low': quote['l'],
                    'open': quote['o'],
                    'previous_close': quote['pc'],
                    'change': quote['d'],
                    'percent_change': quote['dp']
                }
        except Exception as e:
            pass

        return None

    def get_company_profile(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get company profile from Finnhub (comprehensive, real-time).

        Returns:
            {
                'name': str,
                'ticker': str,
                'exchange': str,
                'industry': str,
                'logo': str (URL),
                'market_cap': float,
                'shares_outstanding': float,
                'ipo': str (date)
            }
        """
        if not self.finnhub_client:
            return None

        try:
            profile = self.finnhub_client.company_profile2(symbol=ticker)

            if profile and profile.get('ticker'):
                return {
                    'name': profile.get('name', 'Unknown'),
                    'ticker': profile.get('ticker', ticker),
                    'exchange': profile.get('exchange', 'Unknown'),
                    'industry': profile.get('finnhubIndustry', 'Unknown'),
                    'sector': profile.get('finnhubIndustry', 'Unknown'),  # Finnhub doesn't separate sector
                    'logo': profile.get('logo', ''),
                    'market_cap': profile.get('marketCapitalization', 0) * 1_000_000,  # Convert to actual number
                    'shares_outstanding': profile.get('shareOutstanding', 0) * 1_000_000,
                    'ipo': profile.get('ipo', 'Unknown'),
                    'weburl': profile.get('weburl', ''),
                    'country': profile.get('country', 'Unknown')
                }
        except Exception as e:
            pass

        return None

    def get_basic_financials(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get basic financial metrics from Finnhub.

        Returns:
            {
                'pe_ratio': float,
                'beta': float,
                'year_high': float,
                'year_low': float,
                'dividend_yield': float,
                'eps': float,
                'revenue_per_share': float
            }
        """
        if not self.finnhub_client:
            return None

        try:
            # Finnhub basic financials
            financials = self.finnhub_client.company_basic_financials(ticker, 'all')

            if financials and 'metric' in financials:
                metrics = financials['metric']

                return {
                    'pe_ratio': metrics.get('peBasicExclExtraTTM', 0) or metrics.get('peNormalizedAnnual', 0),
                    'beta': metrics.get('beta', 0),
                    'year_high': metrics.get('52WeekHigh', 0),
                    'year_low': metrics.get('52WeekLow', 0),
                    'dividend_yield': metrics.get('dividendYieldIndicatedAnnual', 0),
                    'eps': metrics.get('epsBasicExclExtraItemsTTM', 0),
                    'revenue_per_share': metrics.get('revenuePerShareTTM', 0),
                    'peg_ratio': metrics.get('pegRatio', 0),
                    'profit_margin': metrics.get('netProfitMarginTTM', 0),
                    'roe': metrics.get('roeTTM', 0),
                    'roa': metrics.get('roaTTM', 0)
                }
        except Exception as e:
            pass

        return None

    def get_company_news(self, ticker: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        Get company news from Finnhub (real-time).

        Returns:
            List of {
                'headline': str,
                'source': str,
                'url': str,
                'summary': str,
                'datetime': int (unix timestamp)
            }
        """
        if not self.finnhub_client:
            return []

        try:
            from datetime import datetime, timedelta

            # Get news from last 7 days
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)

            news = self.finnhub_client.company_news(
                ticker,
                _from=start_date.strftime('%Y-%m-%d'),
                to=end_date.strftime('%Y-%m-%d')
            )

            if news:
                return [
                    {
                        'headline': item.get('headline', ''),
                        'source': item.get('source', ''),
                        'url': item.get('url', ''),
                        'summary': item.get('summary', ''),
                        'datetime': item.get('datetime', 0)
                    }
                    for item in news[:limit]
                ]
        except Exception as e:
            pass

        return []

    def get_recommendation_trends(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get analyst recommendations from Finnhub.

        Returns:
            {
                'buy': int,
                'hold': int,
                'sell': int,
                'strong_buy': int,
                'strong_sell': int
            }
        """
        if not self.finnhub_client:
            return None

        try:
            recommendations = self.finnhub_client.recommendation_trends(ticker)

            if recommendations and len(recommendations) > 0:
                latest = recommendations[0]  # Most recent month

                return {
                    'buy': latest.get('buy', 0),
                    'hold': latest.get('hold', 0),
                    'sell': latest.get('sell', 0),
                    'strong_buy': latest.get('strongBuy', 0),
                    'strong_sell': latest.get('strongSell', 0),
                    'period': latest.get('period', '')
                }
        except Exception as e:
            pass

        return None


# Global instance
@st.cache_resource
def get_hybrid_fetcher() -> HybridDataFetcher:
    """Get or create hybrid data fetcher instance."""
    return HybridDataFetcher()


# Convenience functions
@st.cache_data(ttl=5)  # 5 second cache for real-time quotes
def get_realtime_quote(ticker: str) -> Optional[Dict[str, float]]:
    """Get real-time quote."""
    fetcher = get_hybrid_fetcher()
    return fetcher.get_real_time_quote(ticker)


@st.cache_data(ttl=3600)  # 1 hour cache for company profile
def get_company_overview_hybrid(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Get comprehensive company overview from multiple sources.
    Combines Finnhub profile + financials for complete picture.
    """
    fetcher = get_hybrid_fetcher()

    # Get profile
    profile = fetcher.get_company_profile(ticker)
    if not profile:
        return None

    # Get financials
    financials = fetcher.get_basic_financials(ticker)

    # Get recommendations
    recommendations = fetcher.get_recommendation_trends(ticker)

    # Combine everything
    overview = {
        'source': 'Finnhub',
        'name': profile['name'],
        'ticker': profile['ticker'],
        'sector': profile['sector'],
        'industry': profile['industry'],
        'description': f"{profile['name']} is a {profile['industry']} company listed on {profile['exchange']}.",
        'market_cap': profile['market_cap'],
        'logo': profile['logo'],
        'weburl': profile['weburl'],
        'country': profile['country'],
        'ipo': profile['ipo']
    }

    # Add financials if available
    if financials:
        overview.update({
            'pe_ratio': financials['pe_ratio'],
            'peg_ratio': financials['peg_ratio'],
            'beta': financials['beta'],
            'year_high': financials['year_high'],
            'year_low': financials['year_low'],
            'dividend_yield': financials['dividend_yield'],
            'eps': financials['eps'],
            'profit_margin': financials['profit_margin'],
            'roe': financials['roe'],
            'roa': financials['roa']
        })
    else:
        # Defaults
        overview.update({
            'pe_ratio': 0,
            'peg_ratio': 0,
            'beta': 0,
            'year_high': 0,
            'year_low': 0,
            'dividend_yield': 0,
            'eps': 0,
            'profit_margin': 0,
            'roe': 0,
            'roa': 0
        })

    # Add analyst target price from recommendations
    if recommendations:
        total_analysts = (recommendations['strong_buy'] + recommendations['buy'] +
                         recommendations['hold'] + recommendations['sell'] +
                         recommendations['strong_sell'])

        # Calculate weighted target (this is approximate)
        overview['analyst_count'] = total_analysts
        overview['analyst_strong_buy'] = recommendations['strong_buy']
        overview['analyst_buy'] = recommendations['buy']
        overview['analyst_hold'] = recommendations['hold']
        overview['analyst_sell'] = recommendations['sell']
        overview['analyst_strong_sell'] = recommendations['strong_sell']

    return overview


@st.cache_data(ttl=300)  # 5 minute cache for news
def get_company_news_hybrid(ticker: str, limit: int = 10) -> List[str]:
    """Get company news headlines."""
    fetcher = get_hybrid_fetcher()
    news = fetcher.get_company_news(ticker, limit)

    return [item['headline'] for item in news if item['headline']]
