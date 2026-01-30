"""
OPTIMAL HYBRID DATA STRATEGY
- Finnhub: Real-time price (the big number)
- yfinance: Charts + Fundamentals (smoother, complete)
- Alpha Vantage: Sentiment + Market Movers
- Alpaca: Trading only
"""

import streamlit as st
import finnhub
import yfinance as yf
import pandas as pd
from typing import Optional, Dict, Any
from datetime import datetime


@st.cache_resource
def get_finnhub_client():
    """Get Finnhub client for real-time quotes."""
    try:
        api_key = st.secrets.get("finnhub", {}).get("api_key")
        if api_key:
            return finnhub.Client(api_key=api_key)
    except:
        pass
    return None


@st.cache_data(ttl=5)  # 5 second cache for SPEED
def get_realtime_price(ticker: str) -> Optional[Dict[str, float]]:
    """
    Get REAL-TIME price from Finnhub (the big number).
    This is the fastest, most reliable source for current price.

    Returns:
        {
            'current': float,
            'change': float,
            'percent_change': float,
            'high': float,
            'low': float,
            'open': float,
            'previous_close': float
        }
    """
    client = get_finnhub_client()
    if not client:
        return None

    try:
        quote = client.quote(ticker)

        if quote and quote.get('c', 0) > 0:
            return {
                'current': quote['c'],
                'change': quote['d'],
                'percent_change': quote['dp'],
                'high': quote['h'],
                'low': quote['l'],
                'open': quote['o'],
                'previous_close': quote['pc']
            }
    except:
        pass

    return None


@st.cache_data(ttl=3600)  # 1 hour cache
def get_company_fundamentals(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Get COMPREHENSIVE fundamentals from yfinance.
    yfinance wins here - rich business descriptions, sector, full ratios.

    Returns complete company profile with all metrics.
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        # Verify we got real data
        if not info or 'symbol' not in info:
            return None

        # Calculate dividend yield
        div_rate = info.get("dividendRate", 0) or 0
        current_price = info.get("currentPrice", 0) or info.get("regularMarketPrice", 1) or 1
        div_yield = (div_rate / current_price * 100) if current_price > 0 else 0

        return {
            'source': 'yfinance',
            'name': info.get('longName', ticker),
            'sector': info.get('sector', 'Unknown'),
            'industry': info.get('industry', 'Unknown'),
            'description': info.get('longBusinessSummary', 'No description available.'),
            'website': info.get('website', ''),
            'country': info.get('country', 'Unknown'),

            # Valuation
            'market_cap': info.get('marketCap', 0) or 0,
            'pe_ratio': info.get('trailingPE', 0) or 0,
            'forward_pe': info.get('forwardPE', 0) or 0,
            'peg_ratio': info.get('pegRatio', 0) or 0,
            'price_to_book': info.get('priceToBook', 0) or 0,
            'price_to_sales': info.get('priceToSalesTrailing12Months', 0) or 0,

            # Profitability
            'profit_margin': (info.get('profitMargins', 0) or 0) * 100,
            'operating_margin': (info.get('operatingMargins', 0) or 0) * 100,
            'roe': (info.get('returnOnEquity', 0) or 0) * 100,
            'roa': (info.get('returnOnAssets', 0) or 0) * 100,

            # Financial Health
            'revenue': info.get('totalRevenue', 0) or 0,
            'revenue_growth': (info.get('revenueGrowth', 0) or 0) * 100,
            'earnings_growth': (info.get('earningsGrowth', 0) or 0) * 100,
            'debt_to_equity': info.get('debtToEquity', 0) or 0,
            'current_ratio': info.get('currentRatio', 0) or 0,

            # Per Share
            'eps': info.get('trailingEps', 0) or 0,
            'book_value': info.get('bookValue', 0) or 0,
            'revenue_per_share': info.get('revenuePerShare', 0) or 0,

            # Dividends
            'dividend_yield': div_yield,
            'dividend_rate': div_rate,
            'payout_ratio': (info.get('payoutRatio', 0) or 0) * 100,

            # Risk
            'beta': info.get('beta', 0) or 0,

            # Price Ranges
            'year_high': info.get('fiftyTwoWeekHigh', 0) or 0,
            'year_low': info.get('fiftyTwoWeekLow', 0) or 0,
            'day_high': info.get('dayHigh', 0) or 0,
            'day_low': info.get('dayLow', 0) or 0,

            # Analyst Targets
            'target_mean': info.get('targetMeanPrice', 0) or 0,
            'target_high': info.get('targetHighPrice', 0) or 0,
            'target_low': info.get('targetLowPrice', 0) or 0,
            'recommendation': info.get('recommendationKey', 'none'),

            # Volume
            'volume': info.get('volume', 0) or 0,
            'avg_volume': info.get('averageVolume', 0) or 0,

            # Shares
            'shares_outstanding': info.get('sharesOutstanding', 0) or 0,
            'float_shares': info.get('floatShares', 0) or 0,
        }

    except Exception as e:
        return None


@st.cache_data(ttl=60)  # 1 minute cache for charts
def get_chart_data_yfinance(ticker: str, period: str = "1y", interval: str = "1d") -> Optional[pd.DataFrame]:
    """
    Get SMOOTH CHART DATA from yfinance.
    yfinance wins for charts - aggregates all exchanges, no gaps.

    Returns OHLCV dataframe with complete data.
    """
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)

        if df is not None and not df.empty:
            return df

    except Exception as e:
        pass

    return None


# Export convenience functions
def get_optimal_overview(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Get the BEST of both worlds:
    - Real-time price from Finnhub
    - Fundamentals from yfinance
    """
    # Get fundamentals from yfinance
    overview = get_company_fundamentals(ticker)
    if not overview:
        return None

    # Overlay real-time price from Finnhub
    realtime = get_realtime_price(ticker)
    if realtime:
        overview['realtime_price'] = realtime['current']
        overview['realtime_change'] = realtime['change']
        overview['realtime_change_pct'] = realtime['percent_change']
        overview['realtime_source'] = 'Finnhub'
    else:
        # Fallback to yfinance current price
        overview['realtime_price'] = overview.get('day_high', 0)  # Approximate
        overview['realtime_change'] = 0
        overview['realtime_change_pct'] = 0
        overview['realtime_source'] = 'yfinance (delayed)'

    return overview
