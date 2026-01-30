"""
Unified Market Data Fetcher using Alpaca
Replaces yfinance to avoid rate limiting
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import pytz


class AlpacaDataFetcher:
    """Fetches market data from Alpaca's free data API."""

    def __init__(self):
        self.stock_client = None
        self._initialize()

    def _initialize(self):
        """Initialize Alpaca data client."""
        try:
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
            from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
            from alpaca.data.enums import DataFeed

            api_key = st.secrets["alpaca"]["api_key"]
            secret_key = st.secrets["alpaca"]["secret_key"]

            self.stock_client = StockHistoricalDataClient(
                api_key=api_key,
                secret_key=secret_key
            )
            self.TimeFrame = TimeFrame
            self.TimeFrameUnit = TimeFrameUnit
            self.StockBarsRequest = StockBarsRequest
            self.StockLatestQuoteRequest = StockLatestQuoteRequest
            self.DataFeed = DataFeed
        except Exception as e:
            st.warning(f"Alpaca data client initialization failed: {e}")
            self.stock_client = None

    def is_available(self) -> bool:
        """Check if data client is available."""
        return self.stock_client is not None

    def get_bars(self, ticker: str, period: str = "1y", interval: str = "1d") -> Optional[pd.DataFrame]:
        """
        Fetch historical bars for a ticker.

        Args:
            ticker: Stock symbol (e.g., "AAPL")
            period: Time period - "1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y"
            interval: Bar interval - "1m", "5m", "15m", "30m", "1h", "1d", "1w"

        Returns:
            DataFrame with OHLCV data
        """
        if not self.stock_client:
            return None

        try:
            # Convert period to start date
            now = datetime.now(pytz.UTC)
            period_map = {
                "1d": timedelta(days=1),
                "5d": timedelta(days=5),
                "1mo": timedelta(days=30),
                "3mo": timedelta(days=90),
                "6mo": timedelta(days=180),
                "1y": timedelta(days=365),
                "2y": timedelta(days=730),
                "5y": timedelta(days=1825),
            }
            start = now - period_map.get(period, timedelta(days=365))

            # Convert interval to TimeFrame
            if interval == "1m":
                timeframe = self.TimeFrame.Minute
            elif interval == "5m":
                timeframe = self.TimeFrame(5, self.TimeFrameUnit.Minute)
            elif interval == "15m":
                timeframe = self.TimeFrame(15, self.TimeFrameUnit.Minute)
            elif interval == "30m":
                timeframe = self.TimeFrame(30, self.TimeFrameUnit.Minute)
            elif interval == "1h":
                timeframe = self.TimeFrame.Hour
            elif interval == "1d":
                timeframe = self.TimeFrame.Day
            elif interval == "1w":
                timeframe = self.TimeFrame.Week
            else:
                timeframe = self.TimeFrame.Day

            request = self.StockBarsRequest(
                symbol_or_symbols=ticker.upper(),
                timeframe=timeframe,
                start=start,
                end=now,
                feed=self.DataFeed.IEX  # Use IEX feed (free tier)
            )

            bars = self.stock_client.get_stock_bars(request)

            if not bars or ticker.upper() not in bars.data:
                return None

            # Convert to DataFrame
            data = []
            for bar in bars[ticker.upper()]:
                data.append({
                    'timestamp': bar.timestamp,
                    'Open': float(bar.open),
                    'High': float(bar.high),
                    'Low': float(bar.low),
                    'Close': float(bar.close),
                    'Volume': int(bar.volume)
                })

            if not data:
                return None

            df = pd.DataFrame(data)
            df.set_index('timestamp', inplace=True)
            df.index = pd.to_datetime(df.index)

            return df

        except Exception as e:
            st.warning(f"Error fetching data for {ticker}: {e}")
            return None

    def get_latest_price(self, ticker: str) -> Optional[float]:
        """Get the latest price for a ticker."""
        if not self.stock_client:
            return None

        try:
            from alpaca.data.requests import StockLatestBarRequest

            # Use latest bar instead of quote (more reliable on free tier)
            request = StockLatestBarRequest(
                symbol_or_symbols=ticker.upper(),
                feed=self.DataFeed.IEX
            )
            bars = self.stock_client.get_stock_latest_bar(request)

            if ticker.upper() in bars:
                return float(bars[ticker.upper()].close)
            return None
        except Exception as e:
            # Fallback: get last bar from historical data
            try:
                data = self.get_bars(ticker, period="5d", interval="1d")
                if data is not None and not data.empty:
                    return float(data['Close'].iloc[-1])
            except:
                pass
            return None

    def get_multiple_bars(self, tickers: List[str], period: str = "1y",
                          interval: str = "1d") -> dict:
        """Fetch bars for multiple tickers at once."""
        if not self.stock_client:
            return {}

        try:
            now = datetime.now(pytz.UTC)
            period_map = {
                "1d": timedelta(days=1),
                "5d": timedelta(days=5),
                "1mo": timedelta(days=30),
                "3mo": timedelta(days=90),
                "6mo": timedelta(days=180),
                "1y": timedelta(days=365),
            }
            start = now - period_map.get(period, timedelta(days=365))

            # Convert interval to TimeFrame
            if interval == "1d":
                timeframe = self.TimeFrame.Day
            elif interval == "1h":
                timeframe = self.TimeFrame.Hour
            else:
                timeframe = self.TimeFrame.Day

            request = self.StockBarsRequest(
                symbol_or_symbols=[t.upper() for t in tickers],
                timeframe=timeframe,
                start=start,
                end=now,
                feed=self.DataFeed.IEX  # Use IEX feed (free tier)
            )

            bars = self.stock_client.get_stock_bars(request)

            results = {}
            for ticker in tickers:
                ticker_upper = ticker.upper()
                if ticker_upper in bars.data:
                    data = []
                    for bar in bars[ticker_upper]:
                        data.append({
                            'timestamp': bar.timestamp,
                            'Open': float(bar.open),
                            'High': float(bar.high),
                            'Low': float(bar.low),
                            'Close': float(bar.close),
                            'Volume': int(bar.volume)
                        })
                    if data:
                        df = pd.DataFrame(data)
                        df.set_index('timestamp', inplace=True)
                        df.index = pd.to_datetime(df.index)
                        results[ticker_upper] = df

            return results

        except Exception as e:
            st.warning(f"Error fetching multiple tickers: {e}")
            return {}


@st.cache_resource
def get_data_fetcher() -> AlpacaDataFetcher:
    """Get or create data fetcher instance."""
    return AlpacaDataFetcher()


def fetch_stock_data(ticker: str, period: str = "1y", interval: str = "1d") -> Optional[pd.DataFrame]:
    """
    Convenience function to fetch stock data.
    This is the main function to use throughout the app.
    """
    fetcher = get_data_fetcher()
    return fetcher.get_bars(ticker, period, interval)


def fetch_latest_price(ticker: str) -> Optional[float]:
    """Convenience function to get latest price."""
    fetcher = get_data_fetcher()
    return fetcher.get_latest_price(ticker)


@st.cache_data(ttl=3600)  # Cache for 1 hour to save API calls
def get_company_overview(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Fetch rich company data from Alpha Vantage OVERVIEW endpoint.
    Falls back to yfinance if API limit reached or unavailable.

    Returns:
        {
            'source': str,
            'description': str,
            'sector': str,
            'industry': str,
            'pe_ratio': float,
            'peg_ratio': float,
            'market_cap': int,
            'dividend_yield': float (as percentage),
            'target_price': float,
            'year_high': float,
            'year_low': float,
            'beta': float,
            'eps': float,
            'revenue': int,
            'profit_margin': float
        }
    """
    import requests

    # 1. Try Alpha Vantage First (Rich Data)
    try:
        api_key = st.secrets.get("alphavantage", {}).get("api_key")

        if api_key:
            url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker}&apikey={api_key}"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                av_data = response.json()

                # Check if valid response (Alpha Vantage returns {} or "Note" on rate limit)
                if "Symbol" in av_data and av_data.get("Symbol"):
                    return {
                        "source": "Alpha Vantage",
                        "description": av_data.get("Description", "No description available."),
                        "sector": av_data.get("Sector", "Unknown"),
                        "industry": av_data.get("Industry", "Unknown"),
                        "pe_ratio": float(av_data.get("PERatio", 0) or 0),
                        "peg_ratio": float(av_data.get("PEGRatio", 0) or 0),
                        "market_cap": int(av_data.get("MarketCapitalization", 0) or 0),
                        "dividend_yield": float(av_data.get("DividendYield", 0) or 0) * 100,
                        "target_price": float(av_data.get("AnalystTargetPrice", 0) or 0),
                        "year_high": float(av_data.get("52WeekHigh", 0) or 0),
                        "year_low": float(av_data.get("52WeekLow", 0) or 0),
                        "beta": float(av_data.get("Beta", 0) or 0),
                        "eps": float(av_data.get("EPS", 0) or 0),
                        "revenue": int(av_data.get("RevenueTTM", 0) or 0),
                        "profit_margin": float(av_data.get("ProfitMargin", 0) or 0) * 100
                    }

    except Exception as e:
        # Silent fallback to yfinance
        pass

    # 2. Fallback to yfinance (Basic Data)
    try:
        import yfinance as yf
        import requests

        # Use clean session with User-Agent
        clean_session = requests.Session()
        clean_session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        stock = yf.Ticker(ticker, session=clean_session)
        info = stock.info

        # Calculate dividend yield manually
        div_rate = info.get("dividendRate", 0) or 0
        current_price = info.get("currentPrice", 0) or info.get(
            "regularMarketPrice", 0) or 1
        div_yield = (div_rate / current_price *
                     100) if current_price > 0 else 0

        return {
            "source": "yfinance (Backup)",
            "description": info.get("longBusinessSummary", "No description available."),
            "sector": info.get("sector", "Unknown"),
            "industry": info.get("industry", "Unknown"),
            "pe_ratio": float(info.get("trailingPE", 0) or 0),
            "peg_ratio": float(info.get("pegRatio", 0) or 0),
            "market_cap": int(info.get("marketCap", 0) or 0),
            "dividend_yield": div_yield,
            "target_price": float(info.get("targetMeanPrice", 0) or 0),
            "year_high": float(info.get("fiftyTwoWeekHigh", 0) or 0),
            "year_low": float(info.get("fiftyTwoWeekLow", 0) or 0),
            "beta": float(info.get("beta", 0) or 0),
            "eps": float(info.get("trailingEps", 0) or 0),
            "revenue": int(info.get("totalRevenue", 0) or 0),
            "profit_margin": float(info.get("profitMargins", 0) or 0) * 100
        }

    except Exception as e:
        # Both sources failed - return basic fallback
        pass

    # 3. Last resort: return minimal placeholder
    return {
        "source": "Placeholder (API limit reached)",
        "description": f"Company data temporarily unavailable. Alpha Vantage API limit: 25 calls/day.",
        "sector": "Technology",
        "industry": "Semiconductors",
        "pe_ratio": 0,
        "peg_ratio": 0,
        "market_cap": 0,
        "dividend_yield": 0,
        "target_price": 0,
        "year_high": 0,
        "year_low": 0,
        "beta": 0,
        "eps": 0,
        "revenue": 0,
        "profit_margin": 0
    }
