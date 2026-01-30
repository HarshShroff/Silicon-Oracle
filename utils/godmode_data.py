"""
GOD MODE DATA LAYER
Squeezes maximum value from all free tiers:
- Finnhub: Real-time quotes, peers, earnings, insider trades, rec trends
- Alpaca: UNLIMITED Benzinga news feed
- Alpha Vantage: Sentiment scoring (rate limited)
- yfinance: Deep fundamentals + smooth charts
"""

import streamlit as st
import finnhub
import pandas as pd
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import yfinance as yf


# ============================================
# FINVIZ: STEALTH SCRAPER (Layer 2)
# ============================================

def get_finviz_data(ticker):
    """
    Scrapes fundamental data from Finviz.
    No API key required. Mimics a browser to get P/E, PEG, Target Price.
    """
    try:
        import requests
        url = f"https://finviz.com/quote.ashx?t={ticker}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

        # Requests allows us to set the User-Agent (so we don't get blocked)
        r = requests.get(url, headers=headers)

        # Pandas can read HTML tables directly!
        tables = pd.read_html(r.text)

        # The main data is usually in the snapshot table
        # We look for a table that contains 'P/E'
        df = None
        for t in tables:
            if 'P/E' in t.values:
                df = t
                break

        if df is None:
            return {}

        # Finviz tables are weird (col 0 is label, col 1 is value, col 2 is label...)
        # We flatten it into a simple dictionary
        data = {}
        # Iterate through pairs of columns
        for i in range(0, len(df.columns), 2):
            keys = df.iloc[:, i]
            values = df.iloc[:, i+1]
            for k, v in zip(keys, values):
                data[str(k)] = v

        # Helper to safely clean numbers
        def clean_num(val):
            if not isinstance(val, str):
                return val
            val = val.replace('%', '').replace(',', '')
            if val == '-':
                return None
            try:
                if 'B' in val:
                    return float(val.replace('B', '')) * 1e9
                if 'M' in val:
                    return float(val.replace('M', '')) * 1e6
                if 'T' in val:
                    return float(val.replace('T', '')) * 1e12
                return float(val)
            except:
                return None

        return {
            "market_cap": clean_num(data.get('Market Cap')),
            "pe_ratio": clean_num(data.get('P/E')),
            "peg_ratio": clean_num(data.get('PEG')),
            "beta": clean_num(data.get('Beta')),
            "dividend_yield": clean_num(data.get('Dividend %')),
            "target_mean": clean_num(data.get('Target Price')),
            "year_high": clean_num(data.get('52W High')),
            "year_low": clean_num(data.get('52W Low')),
            "recommendation": data.get('Recom')  # 1.0 is Strong Buy, 5.0 Sell
        }

    except Exception:
        return {}

# ============================================
# FINNHUB: REAL-TIME + INTELLIGENCE
# ============================================


# Removed cache_resource because client depends on user session (BYOK)
def get_finnhub_client():
    """Get Finnhub client (60 calls/min free tier)."""
    try:
        # AUTO-FIX: Use BYOK keys if available
        from utils.auth import get_user_decrypted_keys, is_logged_in

        api_key = None
        if is_logged_in():
            user_keys = get_user_decrypted_keys()
            api_key = user_keys.get("finnhub_api_key")

        if not api_key:
            api_key = st.secrets.get("finnhub", {}).get("api_key")

        if api_key:
            return finnhub.Client(api_key=api_key)
    except:
        pass
    return None


@st.cache_data(ttl=5)  # 5 second cache for SPEED
def get_realtime_quote(ticker: str) -> Optional[Dict[str, float]]:
    """
    FINNHUB: Real-time price (THE BIG NUMBER).
    Returns: current, change, percent_change, high, low, open, previous_close
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


@st.cache_data(ttl=300)  # 5 minute cache
def get_market_status(exchange: str = "US") -> Optional[Dict[str, Any]]:
    """
    FINNHUB: Market Open/Close Status.
    Returns: isOpen, session, holiday, etc.
    """
    client = get_finnhub_client()
    if not client:
        return None

    try:
        status = client.market_status(exchange=exchange)
        if status:
            return {
                "is_open": status.get("isOpen", False),
                "session": status.get("session", "N/A"),
                "holiday": status.get("holiday", None),
                "exchange": status.get("exchange", exchange)
            }
    except:
        pass
    return None


@st.cache_data(ttl=3600)  # 1 hour cache
def get_company_peers(ticker: str) -> Optional[List[str]]:
    """
    FINNHUB: Competitor tickers.
    "If you like NVDA, check out: AMD, INTC, TSM..."
    """
    client = get_finnhub_client()
    if not client:
        return None

    try:
        peers = client.company_peers(ticker)
        # Returns list like ['AMD', 'INTC', 'TSM', 'MU']
        if peers and isinstance(peers, list):
            # Remove the ticker itself and limit to top 5
            peers = [p for p in peers if p != ticker][:5]
            return peers
    except:
        pass
    return None


@st.cache_data(ttl=3600)  # 1 hour cache
def get_earnings_calendar(ticker: str) -> Optional[Dict[str, Any]]:
    """
    FINNHUB: Next earnings date + estimates.
    "Q1 2026 earnings on Feb 24, EPS est: $0.85"
    """
    client = get_finnhub_client()
    if not client:
        return None

    try:
        # Get earnings calendar for next 30 days
        today = datetime.now()
        from_date = today.strftime('%Y-%m-%d')
        to_date = (today + timedelta(days=90)).strftime('%Y-%m-%d')

        calendar = client.earnings_calendar(
            _from=from_date, to=to_date, symbol=ticker
        )

        entries = calendar.get('earningsCalendar', [])
        if entries:
            # Sort by date and pick first one
            next_earn = sorted(entries, key=lambda x: x['date'])[0]
            return {
                'date': next_earn.get('date'),
                'quarter': next_earn.get('quarter'),
                'year': next_earn.get('year'),
                'eps_estimate': next_earn.get('epsEstimate')
            }
    except:
        pass
    return None


@st.cache_data(ttl=3600)
def get_insider_transactions(ticker: str) -> Optional[List[Dict[str, Any]]]:
    """
    FINNHUB: Recent insider trades.
    "Jensen Huang SOLD 500k shares"
    """
    client = get_finnhub_client()
    if not client:
        return None

    try:
        data = client.stock_insider_transactions(ticker)
        transactions = data.get('data', [])
        if transactions:
            return transactions[:10]  # Raw data, processed in UI
    except:
        pass
    return None


@st.cache_data(ttl=3600)
def get_recommendation_trends(ticker: str) -> Optional[List[Dict[str, Any]]]:
    """
    FINNHUB: Analyst buy/sell ratings.
    "Strong Buy: 15, Buy: 20..."
    """
    client = get_finnhub_client()
    if not client:
        return None

    try:
        trends = client.recommendation_trends(ticker)
        if trends:
            return trends  # Raw list
    except:
        pass
    return None


@st.cache_data(ttl=3600)
def get_price_targets(ticker: str) -> Optional[Dict[str, float]]:
    """
    FINNHUB: Analyst price targets.
    "Target High: $150, Mean: $148"
    """
    client = get_finnhub_client()
    if not client:
        return None

    try:
        targets = client.price_target(ticker)
        if targets:
            return {
                'target_high': targets.get('targetHigh', 0),
                'target_low': targets.get('targetLow', 0),
                'target_mean': targets.get('targetMean', 0),
                'last_updated': targets.get('lastUpdated', '')
            }
    except:
        pass
    return None


# ============================================
# GOOGLE NEWS (RSS - The Firehose)
# ============================================

@st.cache_data(ttl=60)
def get_google_news(ticker: str) -> Optional[List[Dict[str, Any]]]:
    """
    Fetches latest news from Google News RSS Feed.
    Advantages: Aggregates ALL sources (CNBC, Reuters, Bloomberg), Real-time, No banning.
    """
    try:
        import feedparser
        import urllib.parse

        # 1. Construct the Search URL (e.g., "NVDA stock news")
        query = urllib.parse.quote(f"{ticker} stock news")
        rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

        # 2. Parse the Feed
        feed = feedparser.parse(rss_url)

        news_items = []
        for entry in feed.entries[:10]:  # Get top 10 stories
            news_items.append({
                'headline': entry.title,
                'url': entry.link,
                'summary': entry.source.title if 'source' in entry else 'Google News',
                'author': 'Google News',
                'created_at': entry.published,
                'symbols': [ticker]
            })

        return news_items
    except Exception:
        return []

# ============================================
# ALPACA: UNLIMITED NEWS
# ============================================


@st.cache_data(ttl=60)  # 60 second cache!
def get_alpaca_news(ticker: str, limit: int = 10) -> Optional[List[Dict[str, Any]]]:
    """
    ALPACA (Benzinga): Real-time news feed.
    Much faster/better than yfinance news.
    """
    try:
        from utils.alpaca import get_alpaca_trader
        trader = get_alpaca_trader()
        if trader.is_connected():
            news_items = trader.get_news(ticker, limit=limit)
            # Convert objects to dicts matching UI expectation
            results = []
            for n in news_items:
                results.append({
                    'headline': n.headline,
                    'summary': n.summary,
                    'author': n.author,
                    'created_at': n.created_at,
                    'url': n.url,
                    'symbols': n.symbols
                })
            return results
    except Exception as e:
        pass

    return None


@st.cache_data(ttl=300)  # 5 min cache
def get_market_movers() -> Optional[Dict[str, pd.DataFrame]]:
    """
    ALPACA: Top Gainers & Losers (God Mode).
    Uses the unmetered Data API.
    """
    try:
        import requests

        # AUTO-FIX: Use BYOK keys if available
        from utils.auth import get_user_decrypted_keys, is_logged_in

        api_key = None
        secret_key = None

        if is_logged_in():
            user_keys = get_user_decrypted_keys()
            api_key = user_keys.get("alpaca_api_key")
            secret_key = user_keys.get("alpaca_secret_key")

        # Fallback
        if not api_key:
            api_key = st.secrets.get("alpaca", {}).get("api_key")
            secret_key = st.secrets.get("alpaca", {}).get("secret_key")

        if not api_key or not secret_key:
            return None

        url = "https://data.alpaca.markets/v1beta1/screener/stocks/movers?top=20"
        headers = {
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": secret_key,
            "accept": "application/json"
        }

        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()

            # Map Alpaca response to our DataFrame format
            # Alpaca returns: {"gainers": [...], "losers": [...]}
            # Each item: {"symbol": "NVDA", "price": 123.4, "change_percent": 5.4}

            result = {}
            if "gainers" in data:
                gainers = []
                for item in data["gainers"]:
                    gainers.append({
                        'ticker': item.get('symbol'),
                        'price': item.get('price'),
                        # Alpaca uses percent_change
                        'change_percentage': item.get('percent_change'),
                        'volume': 0  # Alpaca movers endpoint might not return vol, check docs or handle safely
                    })
                result['gainers'] = pd.DataFrame(gainers)

            if "losers" in data:
                losers = []
                for item in data["losers"]:
                    losers.append({
                        'ticker': item.get('symbol'),
                        'price': item.get('price'),
                        'change_percentage': item.get('percent_change'),
                        'volume': 0
                    })
                result['losers'] = pd.DataFrame(losers)

            return result

    except Exception as e:
        pass

    return None


# ============================================
# HYBRID: FUNDAMENTALS & CHARTS
# ============================================

@st.cache_data(ttl=3600)
def get_company_fundamentals(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Hybrid Fetcher:
    - TEXT (Sector, Description): Always tries Yahoo first.
    - NUMBERS (P/E, Targets): Tries Yahoo, fills gaps with Finviz.
    """
    data = {
        "market_cap": 0, "sector": "N/A", "industry": "N/A",
        "summary": "No Data", "pe_ratio": None, "peg_ratio": None,
        "beta": None, "dividend_yield": 0, "target_mean": None,
        "year_high": 0, "year_low": 0
    }

    # --- STEP 1: Get Text & Basic Info from Yahoo ---
    # We do NOT raise an error if this fails completely, we just move on.
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        if info:
            data['sector'] = info.get('sector', 'N/A')
            data['industry'] = info.get('industry', 'N/A')
            data['summary'] = info.get('longBusinessSummary', 'No Data')

            # Try getting numbers from Yahoo while we are here
            data['pe_ratio'] = info.get('trailingPE') or info.get('forwardPE')
            data['peg_ratio'] = info.get('pegRatio')
            data['beta'] = info.get('beta')
            data['dividend_yield'] = (info.get('dividendYield', 0) or 0)
            data['target_mean'] = info.get('targetMeanPrice')
            data['market_cap'] = info.get('marketCap')
            data['year_high'] = info.get('fiftyTwoWeekHigh')
            data['year_low'] = info.get('fiftyTwoWeekLow')
    except Exception:
        pass

    # --- STEP 2: Reinforce Market Cap with Fast Info (It's more reliable) ---
    try:
        stock = yf.Ticker(ticker)
        fast = stock.fast_info
        if fast and fast.market_cap:
            data['market_cap'] = fast.market_cap
            data['year_high'] = fast.year_high
            data['year_low'] = fast.year_low
    except:
        pass

    # --- STEP 3: Fill Numerical Gaps with Finviz ---
    # If we are missing P/E, Targets, or PEG, we call the scraper.
    if not data['pe_ratio'] or not data['target_mean'] or not data['peg_ratio']:
        f_data = get_finviz_data(ticker)

        # Only overwrite if Finviz has data and Yahoo didn't
        if not data['pe_ratio']:
            data['pe_ratio'] = f_data.get('pe_ratio')
        if not data['peg_ratio']:
            data['peg_ratio'] = f_data.get('peg_ratio')
        if not data['target_mean']:
            data['target_mean'] = f_data.get('target_mean')
        if not data['beta']:
            data['beta'] = f_data.get('beta')
        if not data['dividend_yield']:
            data['dividend_yield'] = f_data.get('dividend_yield')

        # If Yahoo totally failed on price/cap, take Finviz's
        if not data['market_cap']:
            data['market_cap'] = f_data.get('market_cap')
        if not data['year_high']:
            data['year_high'] = f_data.get('year_high')
        if not data['year_low']:
            data['year_low'] = f_data.get('year_low')

    data['source'] = "Yahoo/Finviz (Hybrid)"
    return data


@st.cache_data(ttl=60)  # 1 minute cache
def get_chart_data(ticker: str, period: str = "1y", interval: str = "1d") -> Optional[pd.DataFrame]:
    """
    YFINANCE: Smooth chart data (aggregates all exchanges).
    Returns OHLCV dataframe.
    """
    try:
        # Silence yfinance spam
        import logging
        logging.getLogger('yfinance').setLevel(logging.CRITICAL)

        # Let yfinance handle the session (curl_cffi enforced)
        stock = yf.Ticker(ticker)

        df = stock.history(period=period, interval=interval, auto_adjust=False)

        if df is not None and not df.empty:
            return df

    except Exception:
        pass

    return None


# ============================================
# GOD MODE: COMBINED INTELLIGENCE
# ============================================

def get_complete_intelligence(ticker: str) -> Dict[str, Any]:
    """
    GOD MODE: Combine all APIs for maximum intelligence.

    Returns complete package:
    - Real-time quote (Finnhub)
    - Fundamentals (yfinance)
    - News (Alpaca unlimited)
    - Peers (Finnhub)
    - Earnings (Finnhub)
    - Insider trades (Finnhub)
    - Analyst trends (Finnhub)
    - Price targets (Finnhub)
    """

    intelligence = {
        'ticker': ticker,
        'timestamp': datetime.now().isoformat(),
    }

    # 0. Market Status (Finnhub)
    status = get_market_status()
    if status:
        intelligence['market_status'] = status

    # 1. Real-time quote (Finnhub - 5s cache)
    quote = get_realtime_quote(ticker)
    if quote:
        intelligence['quote'] = quote

    # 2. Fundamentals (Triple Threat: Yahoo -> Finviz -> Partial)
    fundamentals = get_company_fundamentals(ticker)
    if fundamentals:
        intelligence['fundamentals'] = fundamentals

    # 3. Technicals (Simple Backup if App analysis fails)
    tech = {}
    try:
        # Let yfinance handle the session
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")
        if not hist.empty:
            # Simple SMA/RSI calc
            sma50 = hist['Close'].rolling(window=50).mean().iloc[-1]
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs)).iloc[-1]
            tech = {"sma_50": sma50, "rsi": rsi}
    except:
        pass
    intelligence['technicals'] = tech

    # 4. News (Tri-Level: Google News -> Alpaca -> Yahoo)
    news = get_google_news(ticker)  # Primary

    if not news:
        news = get_alpaca_news(ticker, limit=10)  # Secondary

    if not news:
        try:
            # Yahoo News Backup (Tertiary)
            ynews = stock.news
            news = [{'headline': n['title'], 'url': n['link'], 'summary': n.get(
                'publisher', 'Yahoo Finance')} for n in ynews[:5]]
        except:
            pass

    if news:
        intelligence['news'] = news

    # 4. Peers (Finnhub - 1h cache)
    peers = get_company_peers(ticker)
    if peers:
        intelligence['peers'] = peers

    # 5. Earnings (Finnhub - 1h cache)
    earnings = get_earnings_calendar(ticker)
    if earnings:
        intelligence['earnings'] = earnings

    # 6. Insider trades (Finnhub - 1h cache)
    insiders = get_insider_transactions(ticker)
    if insiders:
        intelligence['insiders'] = insiders

    # 7. Analyst trends (Finnhub - 1h cache)
    rec_trends = get_recommendation_trends(ticker)
    if rec_trends:
        intelligence['recommendation_trends'] = rec_trends

    # 8. Price targets (Finnhub - 1h cache)
    targets = get_price_targets(ticker)
    if targets:
        intelligence['price_targets'] = targets
    elif 'fundamentals' in intelligence and intelligence['fundamentals'].get('target_mean') != "N/A":
        # Fallback to yfinance data from fundamentals if Finnhub targets failed
        intelligence['price_targets'] = {
            'target_mean': intelligence['fundamentals']['target_mean'],
            'target_high': 0,
            'target_low': 0
        }

    return intelligence
