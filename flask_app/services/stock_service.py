"""
Silicon Oracle - Stock Data Service
Fetches stock data from multiple sources without Streamlit dependencies
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class StockService:
    """Service for fetching and processing stock data."""

    def __init__(self, config: Dict[str, str] = None):
        self.config = config or {}
        self._finnhub_client = None
        self._init_clients()

    def _init_clients(self):
        """Initialize API clients."""
        try:
            import finnhub

            api_key = self.config.get("FINNHUB_API_KEY")
            if api_key:
                self._finnhub_client = finnhub.Client(api_key=api_key)
        except Exception as e:
            logger.warning(f"Failed to initialize Finnhub client: {e}")

    def get_realtime_quote(self, ticker: str) -> Optional[Dict[str, float]]:
        """Get real-time quote from Finnhub."""
        if not self._finnhub_client:
            logger.warning(f"StockService: No Finnhub client for {ticker}. Access denied.")
            return None

        try:
            quote = self._finnhub_client.quote(ticker)
            if quote and quote.get("c", 0) > 0:
                return {
                    "current": quote["c"],
                    "change": quote["d"],
                    "percent_change": quote["dp"],
                    "high": quote["h"],
                    "low": quote["l"],
                    "open": quote["o"],
                    "previous_close": quote["pc"],
                    "source": "finnhub",
                }
        except Exception as e:
            err = str(e)
            if "429" in err:
                logger.debug(f"Finnhub rate limit for {ticker}, falling back to yfinance")
            else:
                logger.warning(f"Finnhub quote failed for {ticker}: {e}")

        return self._get_yfinance_quote(ticker)

    def _get_yfinance_quote(self, ticker: str) -> Optional[Dict[str, float]]:
        """Fallback to yfinance for quote data."""
        try:
            import yfinance as yf

            stock = yf.Ticker(ticker)
            hist = stock.history(period="2d")
            if hist.empty:
                return None

            current = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else current

            return {
                "current": current,
                "change": current - prev,
                "percent_change": ((current - prev) / prev) * 100 if prev else 0,
                "high": float(hist["High"].iloc[-1]),
                "low": float(hist["Low"].iloc[-1]),
                "open": float(hist["Open"].iloc[-1]),
                "previous_close": prev,
                "source": "yfinance",
            }
        except Exception as e:
            logger.error(f"yfinance quote failed for {ticker}: {e}")
            return None

    def get_historical_data(
        self, ticker: str, period: str = "1y", interval: str = "1d"
    ) -> Optional[pd.DataFrame]:
        """Get historical OHLCV data."""
        try:
            import yfinance as yf

            stock = yf.Ticker(ticker)
            df = stock.history(period=period, interval=interval, auto_adjust=False)

            if df is not None and not df.empty:
                return df[["Open", "High", "Low", "Close", "Volume"]]
        except Exception as e:
            logger.error(f"Failed to fetch historical data for {ticker}: {e}")

        return None

    def get_company_info(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get company fundamentals."""
        data = {
            "ticker": ticker,
            "name": "N/A",
            "sector": "N/A",
            "industry": "N/A",
            "market_cap": 0,
            "pe_ratio": None,
            "peg_ratio": None,
            "beta": None,
            "dividend_yield": 0,
            "year_high": 0,
            "year_low": 0,
            "target_price": None,
            "summary": "No data available",
        }

        try:
            import yfinance as yf

            stock = yf.Ticker(ticker)
            info = stock.info

            if info:
                data.update(
                    {
                        "name": info.get("shortName", info.get("longName", ticker)),
                        "sector": info.get("sector", "N/A"),
                        "industry": info.get("industry", "N/A"),
                        "market_cap": info.get("marketCap", 0),
                        "pe_ratio": info.get("trailingPE") or info.get("forwardPE"),
                        "peg_ratio": info.get("pegRatio"),
                        "beta": info.get("beta"),
                        "dividend_yield": info.get("dividendYield", 0) or 0,
                        "year_high": info.get("fiftyTwoWeekHigh", 0),
                        "year_low": info.get("fiftyTwoWeekLow", 0),
                        "target_price": info.get("targetMeanPrice"),
                        "summary": info.get("longBusinessSummary", "No data available"),
                    }
                )
        except Exception as e:
            logger.warning(f"Failed to get company info for {ticker}: {e}")

        return data

    def get_technical_indicators(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Calculate technical indicators."""
        if not self._finnhub_client:
            return None
        df = self.get_historical_data(ticker, period="1y", interval="1d")
        if df is None:
            logger.warning(f"No historical data for {ticker}")
            return None
        if len(df) < 50:
            logger.warning(f"Insufficient data for {ticker}: only {len(df)} rows")
            return None

        try:
            # SMA 50
            sma_50 = df["Close"].rolling(window=50).mean().iloc[-1]

            # RSI 14
            delta = df["Close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = (100 - (100 / (1 + rs))).iloc[-1]

            # Daily returns and volatility
            returns = df["Close"].pct_change().dropna()
            volatility = float(returns.tail(20).std() * np.sqrt(252) * 100)

            # Volume ratio
            avg_volume = df["Volume"].tail(20).mean()
            last_volume = df["Volume"].iloc[-1]
            volume_ratio = float(last_volume / avg_volume) if avg_volume > 0 else 1.0

            # Performance metrics
            current_price = float(df["Close"].iloc[-1])
            perf_1d = float(returns.iloc[-1] * 100) if len(returns) > 0 else 0
            perf_1m = (
                float((current_price / df["Close"].iloc[-21] - 1) * 100) if len(df) > 21 else 0
            )
            perf_3m = (
                float((current_price / df["Close"].iloc[-63] - 1) * 100) if len(df) > 63 else 0
            )

            logger.info(f"Successfully calculated indicators for {ticker}")
            return {
                "price": current_price,
                "sma_50": float(sma_50),
                "rsi": float(rsi),
                "volatility": volatility,
                "volume": int(last_volume),
                "volume_ratio": volume_ratio,
                "daily_change": perf_1d,
                "perf_1m": perf_1m,
                "perf_3m": perf_3m,
            }
        except Exception as e:
            logger.error(f"Failed to calculate indicators for {ticker}: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return None

    def get_market_status(self) -> Dict[str, Any]:
        """Check if market is open."""
        if self._finnhub_client:
            try:
                status = self._finnhub_client.market_status(exchange="US")
                return {
                    "is_open": status.get("isOpen", False),
                    "session": status.get("session", "N/A"),
                    "holiday": status.get("holiday"),
                }
            except Exception:
                pass

        # Fallback: estimate based on time (US Eastern)
        from datetime import datetime, time

        import pytz

        now = datetime.now(pytz.timezone("America/New_York"))
        current_time = now.time()

        # Market hours: Mon-Fri
        is_weekday = now.weekday() < 5

        # Pre-market: 4:00 AM - 9:00 AM ET
        premarket_start = time(4, 0)
        premarket_end = time(9, 0)

        # Regular: 9:00 AM - 4:00 PM ET
        market_start = time(9, 0)
        market_end = time(16, 0)

        # After-hours: 4:00 PM - 8:00 PM ET
        after_start = time(16, 0)
        after_end = time(20, 0)

        if not is_weekday:
            session = "closed"
            is_open = False
        elif premarket_start <= current_time < premarket_end:
            session = "pre-market"
            is_open = True
        elif market_start <= current_time < market_end:
            session = "regular"
            is_open = True
        elif after_start <= current_time < after_end:
            session = "after-hours"
            is_open = True
        else:
            session = "closed"
            is_open = False

        return {"is_open": is_open, "session": session, "holiday": None}

    def get_peers(self, ticker: str) -> List[str]:
        """Get peer companies."""
        if self._finnhub_client:
            try:
                peers = self._finnhub_client.company_peers(ticker)
                if peers:
                    return [p for p in peers if p != ticker][:5]
            except Exception:
                pass
        return []

    def get_earnings(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get next earnings date."""
        if self._finnhub_client:
            try:
                today = datetime.now()
                calendar = self._finnhub_client.earnings_calendar(
                    _from=today.strftime("%Y-%m-%d"),
                    to=(today + timedelta(days=90)).strftime("%Y-%m-%d"),
                    symbol=ticker,
                )
                entries = calendar.get("earningsCalendar", [])
                if entries:
                    next_earn = sorted(entries, key=lambda x: x["date"])[0]
                    return {
                        "date": next_earn.get("date"),
                        "quarter": next_earn.get("quarter"),
                        "year": next_earn.get("year"),
                        "eps_estimate": next_earn.get("epsEstimate"),
                    }
            except Exception:
                pass
        return None

    def get_analyst_recommendations(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """Get analyst recommendations."""
        if self._finnhub_client:
            try:
                return self._finnhub_client.recommendation_trends(ticker)
            except Exception:
                pass
        return None

    def get_price_targets(self, ticker: str) -> Optional[Dict[str, float]]:
        """Get analyst price targets."""
        if self._finnhub_client:
            try:
                targets = self._finnhub_client.price_target(ticker)
                if targets:
                    return {
                        "target_high": targets.get("targetHigh", 0),
                        "target_low": targets.get("targetLow", 0),
                        "target_mean": targets.get("targetMean", 0),
                    }
            except Exception:
                pass
        return None

    def get_insider_trades(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """Get insider trading activity."""
        if self._finnhub_client:
            try:
                data = self._finnhub_client.stock_insider_transactions(ticker)
                trades = data.get("data", [])[:10]

                for trade in trades:
                    # Finnhub often returns value=0; compute from price * share
                    if not trade.get("value") and trade.get("price") and trade.get("share"):
                        trade["value"] = trade["price"] * trade["share"]

                    # Normalize transaction type — Finnhub variants like
                    # "S-Sale!", "S-Sale Ex" must collapse to the canonical
                    # values the frontend filters on.
                    txn = trade.get("transaction", "")
                    if txn.startswith("S-"):
                        trade["transaction"] = "S-Sale"
                    elif txn.startswith("P-"):
                        trade["transaction"] = "P-Purchase"
                    elif txn.startswith("A-"):
                        trade["transaction"] = "A-Award"

                return trades
            except Exception:
                pass
        return None

    def get_news(self, ticker: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get news for ticker from Google News RSS."""
        try:
            import urllib.parse

            import feedparser

            # Add 'when:7d' to ensure fresh news
            query = urllib.parse.quote(f"{ticker} stock news when:7d")
            rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
            feed = feedparser.parse(rss_url)

            news_items = []
            for entry in feed.entries[:limit]:
                news_items.append(
                    {
                        "headline": entry.title,
                        "url": entry.link,
                        "source": entry.source.title if hasattr(entry, "source") else "Google News",
                        "published": entry.published if hasattr(entry, "published") else None,
                    }
                )
            return news_items
        except Exception as e:
            logger.warning(f"Failed to fetch news for {ticker}: {e}")
            return []

    def get_complete_data(self, ticker: str) -> Dict[str, Any]:
        """Get complete stock intelligence package using parallel execution."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # Define tasks
        tasks = {
            "quote": lambda: self.get_realtime_quote(ticker),
            "company": lambda: self.get_company_info(ticker),
            "technicals": lambda: self.get_technical_indicators(ticker),
            "market_status": self.get_market_status,
            "peers": lambda: self.get_peers(ticker),
            "earnings": lambda: self.get_earnings(ticker),
            "recommendations": lambda: self.get_analyst_recommendations(ticker),
            "price_targets": lambda: self.get_price_targets(ticker),
            "insiders": lambda: self.get_insider_trades(ticker),
            "news": lambda: self.get_news(ticker),
        }

        results = {"ticker": ticker, "timestamp": datetime.now().isoformat()}

        # Execute in parallel
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_key = {executor.submit(func): key for key, func in tasks.items()}

            for future in as_completed(future_to_key):
                key = future_to_key[future]
                try:
                    results[key] = future.result()
                except Exception as e:
                    logger.error(f"Error fetching {key} for {ticker}: {e}")
                    results[key] = None

        return results
