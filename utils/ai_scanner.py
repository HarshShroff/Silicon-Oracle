"""
AI Scanner - Enhanced 15-Factor Oracle Scoring System
Tiered smart scanning with Gemini AI integration.
"""
import streamlit as st
import pandas as pd
import numpy as np
import pandas_ta_classic as ta
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import json

# Logging
from utils.logging_config import get_logger, log_performance, log_api_call

logger = get_logger(__name__)


# ============================================
# 15-FACTOR ORACLE SCORING SYSTEM
# ============================================

"""
| # | Factor              | Source        | Weight |
|---|---------------------|---------------|--------|
| 1 | Trend (SMA50)       | yfinance      | 1.0    |
| 2 | Momentum (RSI)      | yfinance      | 1.0    |
| 3 | Market Health (SPY) | yfinance      | 1.0    |
| 4 | Analyst Consensus   | Finnhub       | 1.0    |
| 5 | Insider Activity    | Finnhub       | 1.0    |
| 6 | Price Target Upside | Finnhub/Finviz| 1.0    |
| 7 | Valuation (PEG)     | Yahoo/Finviz  | 1.0    |
| 8 | Earnings Proximity  | Finnhub       | 0.5    |
| 9 | News Sentiment      | Gemini AI     | 1.0    |
| 10| Dividend Yield      | Yahoo         | 0.5    |
| 11| 52-Week Position    | Yahoo         | 0.5    |
| 12| Volume Spike        | yfinance      | 0.5    |
| 13| Sector Momentum     | yfinance      | 0.5    |
| 14| Beta (Volatility)   | Yahoo/Finviz  | 0.5    |
| 15| MACD Signal         | pandas-ta     | 0.5    |
-------------------------------------------------
MAX SCORE: 12.0 points (for stocks with all data available)

DYNAMIC SCORING:
- Scores are calculated as percentage of AVAILABLE factors
- ETFs/funds without certain data (insiders, P/E, etc.) are not penalized
- Final verdict is based on percentage, not absolute score
"""

MAX_ORACLE_SCORE = 12.0  # Theoretical max if all factors have data

# Sector ETF mapping for sector momentum analysis
SECTOR_ETFS = {
    "Technology": "XLK",
    "Financial Services": "XLF",
    "Healthcare": "XLV",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Energy": "XLE",
    "Utilities": "XLU",
    "Industrials": "XLI",
    "Basic Materials": "XLB",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
}


class OracleScanner:
    """
    Enhanced 15-Factor Oracle Scoring System.
    Analyzes stocks using multiple data sources and AI.
    """

    def __init__(self):
        self.cache = {}
        self.spy_data = None
        self.spy_indicators = None
        self.sector_momentum = {}

    def _get_spy_context(self) -> Dict[str, Any]:
        """Fetch and cache SPY data for market context."""
        if self.spy_indicators:
            return self.spy_indicators

        try:
            import yfinance as yf
            spy = yf.Ticker("SPY")
            hist = spy.history(period="1y")

            if hist.empty:
                return {}

            # Calculate SPY indicators
            sma50 = hist['Close'].rolling(50).mean().iloc[-1]
            current = hist['Close'].iloc[-1]
            rsi = self._calculate_rsi(hist['Close'])

            self.spy_indicators = {
                "price": current,
                "sma50": sma50,
                "above_sma50": current > sma50,
                "rsi": rsi,
                "trend": "bullish" if current > sma50 else "bearish"
            }
            return self.spy_indicators
        except Exception:
            return {}

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Calculate RSI from price series."""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return float(rsi.iloc[-1])
        except Exception:
            return 50.0

    def _calculate_macd(self, prices: pd.Series) -> Dict[str, Any]:
        """Calculate MACD indicator."""
        try:
            macd = ta.macd(prices, fast=12, slow=26, signal=9)
            if macd is None or macd.empty:
                return {"signal": "neutral", "histogram": 0}

            # Get column names (they vary by pandas-ta version)
            cols = macd.columns.tolist()
            macd_col = [
                c for c in cols if 'MACD_' in c and 'MACDs' not in c and 'MACDh' not in c][0]
            signal_col = [c for c in cols if 'MACDs_' in c][0]
            hist_col = [c for c in cols if 'MACDh_' in c][0]

            macd_val = macd[macd_col].iloc[-1]
            signal_val = macd[signal_col].iloc[-1]
            histogram = macd[hist_col].iloc[-1]

            # Bullish: MACD crosses above signal line
            # Bearish: MACD crosses below signal line
            signal = "bullish" if macd_val > signal_val else "bearish"

            return {
                "macd": macd_val,
                "signal_line": signal_val,
                "histogram": histogram,
                "signal": signal
            }
        except Exception:
            return {"signal": "neutral", "histogram": 0}

    def _get_sector_momentum(self, sector: str) -> Dict[str, Any]:
        """Get sector ETF momentum."""
        if sector in self.sector_momentum:
            return self.sector_momentum[sector]

        etf = SECTOR_ETFS.get(sector)
        if not etf:
            return {"trend": "neutral", "change_1m": 0}

        try:
            import yfinance as yf
            data = yf.Ticker(etf).history(period="3mo")

            if data.empty:
                return {"trend": "neutral", "change_1m": 0}

            current = data['Close'].iloc[-1]
            month_ago = data['Close'].iloc[-21] if len(
                data) > 21 else data['Close'].iloc[0]
            sma50 = data['Close'].rolling(50).mean(
            ).iloc[-1] if len(data) >= 50 else current

            change_1m = ((current / month_ago) - 1) * 100

            result = {
                "etf": etf,
                "trend": "bullish" if current > sma50 else "bearish",
                "change_1m": change_1m,
                "above_sma50": current > sma50
            }
            self.sector_momentum[sector] = result
            return result
        except Exception:
            return {"trend": "neutral", "change_1m": 0}

    def calculate_oracle_score(self, ticker: str) -> Dict[str, Any]:
        """
        Calculate full 15-factor Oracle score for a ticker.
        Returns detailed breakdown of all factors.

        DYNAMIC SCORING:
        - Tracks both 'score' and 'max_possible_score'
        - Factors with N/A data don't count toward max (prevents ETF penalty)
        - Final verdict based on percentage, not absolute score
        """
        import yfinance as yf
        from utils.godmode_data import (
            get_company_fundamentals, get_recommendation_trends,
            get_insider_transactions, get_price_targets, get_earnings_calendar,
            get_google_news, get_realtime_quote
        )

        factors = {}
        score = 0.0
        max_possible = 0.0  # DYNAMIC: only includes factors with actual data
        reasons = []

        # Helper to add factor with dynamic max tracking
        def add_factor(name: str, value: Any, points: float, max_points: float,
                       detail: str, has_data: bool = True):
            """Add a factor to the scoring system."""
            nonlocal score, max_possible
            factors[name] = {
                "value": value,
                "score": points if has_data else 0,
                "max": max_points if has_data else 0,
                "detail": detail,
                "has_data": has_data
            }
            if has_data:
                score += points
                max_possible += max_points

        try:
            # Fetch base data
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1y")

            if hist.empty:
                return {"ticker": ticker, "score": 0, "error": "No data available"}

            current_price = hist['Close'].iloc[-1]
            fundamentals = get_company_fundamentals(ticker)
            spy_context = self._get_spy_context()

            # ============================================
            # FACTOR 1: Trend (Price vs SMA50) - Weight: 1.0
            # ============================================
            sma50 = hist['Close'].rolling(50).mean(
            ).iloc[-1] if len(hist) >= 50 else None
            if sma50 and not pd.isna(sma50):
                if current_price > sma50:
                    add_factor("trend", "bullish", 1.0, 1.0,
                               f"Price ${current_price:.2f} > SMA50 ${sma50:.2f}")
                    reasons.append("Bullish trend (above SMA50)")
                else:
                    add_factor("trend", "bearish", 0.0,
                               1.0, "Price below SMA50")
            else:
                add_factor("trend", "N/A", 0, 0,
                           "Insufficient history", has_data=False)

            # ============================================
            # FACTOR 2: Momentum (RSI 14) - Weight: 1.0
            # ============================================
            rsi = self._calculate_rsi(hist['Close'])
            if rsi and not pd.isna(rsi):
                if 30 <= rsi <= 70:
                    add_factor("momentum", rsi, 1.0, 1.0,
                               f"RSI {rsi:.0f} in healthy range")
                    reasons.append(f"Healthy momentum (RSI {rsi:.0f})")
                elif rsi < 30:
                    add_factor("momentum", rsi, 0.5, 1.0,
                               f"RSI {rsi:.0f} oversold")
                else:
                    add_factor("momentum", rsi, 0.0, 1.0,
                               f"RSI {rsi:.0f} overbought")
            else:
                add_factor("momentum", "N/A", 0, 0,
                           "No RSI data", has_data=False)

            # ============================================
            # FACTOR 3: Market Health (SPY trend) - Weight: 1.0
            # ============================================
            if spy_context.get("above_sma50"):
                add_factor("market_health", "healthy",
                           1.0, 1.0, "SPY above SMA50")
                reasons.append("Healthy market environment")
            else:
                add_factor("market_health", "weak",
                           0.0, 1.0, "SPY below SMA50")

            # ============================================
            # FACTOR 4: Analyst Consensus - Weight: 1.0
            # ETFs typically don't have analyst coverage - mark as N/A
            # ============================================
            rec_trends = get_recommendation_trends(ticker)
            analyst_has_data = False
            if rec_trends:
                latest = rec_trends[0] if rec_trends else {}
                strong_buy = latest.get('strongBuy', 0)
                buy = latest.get('buy', 0)
                hold = latest.get('hold', 0)
                sell = latest.get('sell', 0)
                strong_sell = latest.get('strongSell', 0)

                total = strong_buy + buy + hold + sell + strong_sell
                if total > 0:
                    analyst_has_data = True
                    bullish_pct = (strong_buy + buy) / total * 100
                    if bullish_pct >= 60:
                        add_factor("analyst", bullish_pct, 1.0, 1.0,
                                   f"{bullish_pct:.0f}% bullish")
                        reasons.append(
                            f"Strong analyst support ({bullish_pct:.0f}% bullish)")
                    elif bullish_pct >= 40:
                        add_factor("analyst", bullish_pct, 0.5, 1.0,
                                   f"{bullish_pct:.0f}% bullish")
                    else:
                        add_factor("analyst", bullish_pct, 0.0, 1.0,
                                   f"Only {bullish_pct:.0f}% bullish")

            if not analyst_has_data:
                # ETFs don't have analysts - N/A, not penalized
                add_factor("analyst", "N/A", 0, 0,
                           "No analyst coverage (ETF/Fund)", has_data=False)

            # ============================================
            # FACTOR 5: Insider Activity - Weight: 1.0
            # ETFs don't have insider trading - mark as N/A
            if not insider_has_data:
                if buys == sells:
                    add_factor("insider", f"{buys}B/{sells}S",
                               0.5, 1.0, "Neutral insider activity")
                else:
                    add_factor("insider", f"{buys}B/{sells}S",
                               0.0, 1.0, "Net insider selling")

            if not insider_has_data:
                # ETFs don't have insiders - N/A, not penalized
                add_factor("insider", "N/A", 0, 0,
                           "No insider data (ETF/Fund)", has_data=False)

            # ============================================
            # FACTOR 6: Price Target Upside - Weight: 1.0
            # ETFs typically don't have price targets - mark as N/A
            # ============================================
            targets = get_price_targets(ticker)
            target_mean = targets.get('target_mean') if targets else None

            if not target_mean and fundamentals:
                target_mean = fundamentals.get('target_mean')

            if target_mean and target_mean > 0:
                upside = ((target_mean / current_price) - 1) * 100
                if upside >= 15:
                    add_factor("target_upside", upside, 1.0, 1.0,
                               f"{upside:.0f}% upside to ${target_mean:.2f}")
                    reasons.append(f"Strong upside potential ({upside:.0f}%)")
                elif upside >= 5:
                    add_factor("target_upside", upside, 0.5,
                               1.0, f"{upside:.0f}% upside")
                else:
                    add_factor("target_upside", upside, 0.0, 1.0,
                               f"Limited upside ({upside:.0f}%)")
            else:
                # No price target is N/A for ETFs
                add_factor("target_upside", "N/A", 0, 0,
                           "No price target (ETF/Fund)", has_data=False)

            # ============================================
            # FACTOR 7: Valuation (PEG ratio) - Weight: 1.0
            # ETFs don't have PEG ratios - mark as N/A
            # ============================================
            peg = fundamentals.get('peg_ratio') if fundamentals else None
            pe = fundamentals.get('pe_ratio') if fundamentals else None

            if peg and isinstance(peg, (int, float)) and peg > 0:
                if peg < 1:
                    add_factor("valuation", peg, 1.0, 1.0,
                               f"PEG {peg:.2f} - Undervalued")
                    reasons.append(f"Attractive valuation (PEG {peg:.2f})")
                elif peg < 2:
                    add_factor("valuation", peg, 0.5, 1.0,
                               f"PEG {peg:.2f} - Fair value")
                else:
                    add_factor("valuation", peg, 0.0, 1.0,
                               f"PEG {peg:.2f} - Expensive")
            elif pe and isinstance(pe, (int, float)) and pe > 0:
                # Fallback to P/E
                if pe < 15:
                    add_factor("valuation", pe, 0.75,
                               1.0, f"P/E {pe:.1f} - Low")
                elif pe < 25:
                    add_factor("valuation", pe, 0.5, 1.0,
                               f"P/E {pe:.1f} - Fair")
                else:
                    add_factor("valuation", pe, 0.25, 1.0,
                               f"P/E {pe:.1f} - High growth")
            else:
                # ETFs don't have valuation metrics - N/A
                add_factor("valuation", "N/A", 0, 0,
                           "No valuation data (ETF/Fund)", has_data=False)

            # ============================================
            # FACTOR 8: Earnings Proximity - Weight: 0.5
            # ETFs don't have earnings - mark as N/A
            # ============================================
            earnings = get_earnings_calendar(ticker)
            if earnings and earnings.get('date'):
                try:
                    earn_date = datetime.strptime(earnings['date'], '%Y-%m-%d')
                    days_until = (earn_date - datetime.now()).days

                    if 7 <= days_until <= 30:
                        add_factor("earnings", days_until, 0.5, 0.5,
                                   f"Earnings in {days_until} days - potential catalyst")
                        reasons.append(
                            f"Earnings catalyst in {days_until} days")
                    elif days_until < 7 and days_until >= 0:
                        add_factor("earnings", days_until, 0.0, 0.5,
                                   f"Earnings imminent ({days_until} days) - risky")
                    elif days_until > 30:
                        add_factor("earnings", days_until, 0.4, 0.5,
                                   f"Earnings in {days_until} days")
                    else:
                        add_factor("earnings", days_until, 0.25,
                                   0.5, "Earnings already passed")
                except Exception:
                    add_factor("earnings", "N/A", 0, 0,
                               "Earnings date unclear", has_data=False)
            else:
                # ETFs don't have earnings - N/A
                add_factor("earnings", "N/A", 0, 0,
                           "No earnings (ETF/Fund)", has_data=False)

            # ============================================
            # FACTOR 9: News Sentiment - Weight: 1.0
            # ============================================
            # FACTOR 9: News Sentiment - Weight: 1.0
            # ============================================
            news = get_google_news(ticker)
            news_has_data = False
            if news and len(news) >= 3:
                # Simple sentiment heuristic
                positive_words = ['surge', 'jump', 'beat', 'growth',
                                  'profit', 'buy', 'upgrade', 'bullish', 'record', 'gain']
                negative_words = ['fall', 'drop', 'miss', 'loss', 'sell',
                                  'downgrade', 'bearish', 'crash', 'decline', 'cut']

                headlines = " ".join(
                    [n.get('headline', '').lower() for n in news[:5]])
                pos_count = sum(1 for w in positive_words if w in headlines)
                neg_count = sum(1 for w in negative_words if w in headlines)
                news_has_data = True

                if pos_count > neg_count:
                    add_factor("sentiment", "positive", 1.0, 1.0,
                               f"Positive news sentiment ({pos_count} bullish signals)")
                    reasons.append("Positive news sentiment")
                elif pos_count == neg_count:
                    add_factor("sentiment", "neutral", 0.5,
                               1.0, "Mixed news sentiment")
                else:
                    add_factor("sentiment", "negative", 0.0, 1.0,
                               f"Negative news sentiment ({neg_count} bearish signals)")

            if not news_has_data:
                add_factor("sentiment", "N/A", 0, 0,
                           "No recent news", has_data=False)

            # ============================================
            # FACTOR 10: Dividend Yield - Weight: 0.5
            # Dividend is optional - no dividend is not penalized
            # ============================================
            div_yield = fundamentals.get(
                'dividend_yield', 0) if fundamentals else 0
            if div_yield and div_yield > 0:
                # yfinance returns dividend yield as decimal (0.03 = 3%)
                if div_yield < 1:
                    div_pct = div_yield * 100
                else:
                    div_pct = div_yield

                if div_pct >= 2:
                    add_factor("dividend", div_pct, 0.5,
                               0.5, f"{div_pct:.2f}% yield")
                    reasons.append(f"Attractive dividend ({div_pct:.2f}%)")
                else:
                    add_factor("dividend", div_pct, 0.25,
                               0.5, f"{div_pct:.2f}% yield")
            else:
                # No dividend is N/A, not penalized (many growth stocks don't pay dividends)
                add_factor("dividend", "N/A", 0, 0,
                           "No dividend", has_data=False)

            # ============================================
            # FACTOR 11: 52-Week Position - Weight: 0.5
            # ============================================
            year_high = fundamentals.get(
                'year_high') if fundamentals else hist['High'].max()
            year_low = fundamentals.get(
                'year_low') if fundamentals else hist['Low'].min()

            if year_high and year_low and year_high > year_low:
                position = (current_price - year_low) / \
                    (year_high - year_low) * 100
                if 20 <= position <= 70:  # Sweet spot
                    add_factor("52w_position", position, 0.5, 0.5,
                               f"{position:.0f}% of 52W range")
                    reasons.append(
                        f"Good entry point ({position:.0f}% of 52W range)")
                elif position < 20:
                    add_factor("52w_position", position, 0.25, 0.5,
                               f"Near 52W low ({position:.0f}%)")
                else:
                    add_factor("52w_position", position, 0.0, 0.5,
                               f"Near 52W high ({position:.0f}%)")
            else:
                add_factor("52w_position", "N/A", 0, 0,
                           "No 52W data", has_data=False)

            # ============================================
            # FACTOR 12: Volume Spike - Weight: 0.5
            # ============================================
            avg_volume = hist['Volume'].tail(20).mean()
            last_volume = hist['Volume'].iloc[-1]
            volume_ratio = last_volume / avg_volume if avg_volume > 0 else 1

            if volume_ratio >= 1.5:
                daily_change = hist['Close'].pct_change().iloc[-1]
                if daily_change > 0:
                    add_factor("volume", volume_ratio, 0.5, 0.5,
                               f"{volume_ratio:.1f}x avg volume (bullish)")
                    reasons.append(
                        f"Volume surge with buying ({volume_ratio:.1f}x)")
                else:
                    add_factor("volume", volume_ratio, 0.0, 0.5,
                               f"{volume_ratio:.1f}x avg volume (bearish)")
            else:
                add_factor("volume", volume_ratio, 0.25, 0.5,
                           f"Normal volume ({volume_ratio:.1f}x)")

            # ============================================
            # FACTOR 13: Sector Momentum - Weight: 0.5
            # ETFs may not have sector data
            # ============================================
            sector = fundamentals.get(
                'sector', 'Unknown') if fundamentals else 'Unknown'
            if sector and sector != 'Unknown':
                sector_data = self._get_sector_momentum(sector)
                if sector_data.get('above_sma50'):
                    add_factor("sector", sector, 0.5, 0.5,
                               f"{sector} sector is bullish ({sector_data.get('change_1m', 0):.1f}% 1M)")
                    reasons.append(f"Strong sector momentum ({sector})")
                else:
                    add_factor("sector", sector, 0.0, 0.5,
                               f"{sector} sector is bearish")
            else:
                # ETFs don't have sector - N/A, not penalized
                add_factor("sector", "N/A", 0, 0,
                           "No sector data (ETF/Fund)", has_data=False)

            # ============================================
            # FACTOR 14: Beta (Volatility) - Weight: 0.5
            # ETFs may not report beta
            # ============================================
            beta = fundamentals.get('beta') if fundamentals else None
            if beta and not pd.isna(beta):
                if 0.5 <= beta <= 1.5:
                    add_factor("beta", beta, 0.5, 0.5,
                               f"Beta {beta:.2f} - Moderate risk")
                elif beta < 0.5:
                    add_factor("beta", beta, 0.25, 0.5,
                               f"Beta {beta:.2f} - Low volatility")
                else:
                    add_factor("beta", beta, 0.0, 0.5,
                               f"Beta {beta:.2f} - High risk")
            else:
                # ETFs may not have beta - N/A, not penalized
                add_factor("beta", "N/A", 0, 0, "No beta data", has_data=False)

            # ============================================
            # FACTOR 15: MACD Signal - Weight: 0.5
            # ============================================
            macd_data = self._calculate_macd(hist['Close'])
            if macd_data:
                if macd_data.get('signal') == 'bullish':
                    add_factor("macd", "bullish", 0.5, 0.5,
                               "MACD bullish crossover")
                    reasons.append("MACD bullish signal")
                else:
                    add_factor("macd", "bearish", 0.0, 0.5, "MACD bearish")
            else:
                add_factor("macd", "N/A", 0, 0, "No MACD data", has_data=False)

            # ============================================
            # FINAL SCORE & VERDICT (DYNAMIC SCORING)
            # ============================================
            # Calculate percentage based on AVAILABLE factors only
            if max_possible > 0:
                score_pct = (score / max_possible) * 100
            else:
                score_pct = 50  # Default to neutral if no data

            # Count available factors for transparency
            available_factors = sum(
                1 for f in factors.values() if f.get('has_data', True))
            total_factors = len(factors)

            # PERCENTAGE-BASED THRESHOLDS (matches app.py Oracle Verdict)
            if score_pct >= 75:
                verdict = "Strong Buy"
            elif score_pct >= 55:
                verdict = "Buy"
            elif score_pct >= 40:
                verdict = "Hold"
            elif score_pct >= 25:
                verdict = "Avoid"
            else:
                verdict = "Strong Sell"

            return {
                "ticker": ticker,
                "score": round(score, 2),
                # DYNAMIC: actual max based on available data
                "max_score": round(max_possible, 2),
                "score_pct": round(score_pct, 1),
                "verdict": verdict,
                "reasons": reasons[:5],  # Top 5 reasons
                "factors": factors,
                "available_factors": available_factors,
                "total_factors": total_factors,
                "current_price": round(current_price, 2),
                "sector": sector if sector != 'Unknown' else 'N/A',
                "scanned_at": datetime.now().isoformat()
            }

        except Exception as e:
            return {
                "ticker": ticker,
                "score": 0,
                "error": str(e),
                "scanned_at": datetime.now().isoformat()
            }

    def get_ai_analysis(self, ticker: str, factors: Dict[str, Any]) -> Optional[str]:
        """
        Get Gemini AI analysis of the stock based on Oracle factors.
        """
        try:
            from utils.gemini import analyze_with_gemini

            prompt = f"""
            Analyze {ticker} based on these Oracle factors:

            Score: {factors.get('score', 0)}/{MAX_ORACLE_SCORE}
            Verdict: {factors.get('verdict', 'Unknown')}

            Key Factors:
            {json.dumps(factors.get('factors', {}), indent=2)}

            Top Reasons:
            {chr(10).join(f"- {r}" for r in factors.get('reasons', []))}

            Provide:
            1. A 2-3 sentence summary of the investment thesis
            2. The #1 risk to watch
            3. A confidence level (1-10)

            Keep it concise and actionable.
            """

            return analyze_with_gemini(prompt)
        except Exception as e:
            return None

    def scan_watchlist(self, tickers: List[str], progress_callback=None) -> List[Dict[str, Any]]:
        """Scan multiple tickers with Oracle scoring."""
        results = []
        start_time = time.time()

        logger.info(
            f"Starting Oracle scan for {len(tickers)} tickers: {', '.join(tickers[:5])}...")

        # Pre-fetch SPY context
        self._get_spy_context()

        total = len(tickers)
        for i, ticker in enumerate(tickers):
            try:
                # logger.debug(f"Scanning ticker {i+1}/{total}: {ticker}")
                result = self.calculate_oracle_score(ticker)
                if result and not result.get('error'):
                    results.append(result)
                    # logger.debug(f"  {ticker}: Score={result.get('score', 0):.1f}, Verdict={result.get('verdict', 'N/A')}")
                else:
                    error_msg = result.get(
                        'error', 'Unknown error') if result else 'No result'
                    logger.warning(f"  {ticker}: Failed - {error_msg}")
            except Exception as e:
                logger.error(f"  {ticker}: Exception - {str(e)}")

            if progress_callback:
                progress_callback((i + 1) / total)

            # Rate limit protection
            time.sleep(0.5)

        # Sort by score descending
        results.sort(key=lambda x: x.get('score', 0), reverse=True)

        elapsed_ms = (time.time() - start_time) * 1000
        log_performance(
            logger, f"Oracle scan ({len(tickers)} tickers)", elapsed_ms)
        logger.info(f"Scan complete: {len(results)}/{len(tickers)} successful")

        return results

    def quick_scan(self, tickers: List[str]) -> List[Dict[str, Any]]:
        """
        Tier 1: Quick scan - basic metrics only.
        Returns stocks worth deep scanning.
        """
        results = []

        for ticker in tickers:
            try:
                import yfinance as yf
                stock = yf.Ticker(ticker)
                hist = stock.history(period="3mo")

                if hist.empty:
                    continue

                current = hist['Close'].iloc[-1]
                sma50 = hist['Close'].rolling(50).mean(
                ).iloc[-1] if len(hist) >= 50 else current
                rsi = self._calculate_rsi(hist['Close'])
                daily_change = hist['Close'].pct_change().iloc[-1] * 100
                volume_ratio = hist['Volume'].iloc[-1] / \
                    hist['Volume'].tail(20).mean()

                # Quick score (0-3)
                quick_score = 0
                if current > sma50:
                    quick_score += 1
                if 30 <= rsi <= 70:
                    quick_score += 1
                if volume_ratio > 1.2:
                    quick_score += 1

                results.append({
                    "ticker": ticker,
                    "price": current,
                    "daily_change": daily_change,
                    "rsi": rsi,
                    "volume_ratio": volume_ratio,
                    "quick_score": quick_score,
                    "worth_deep_scan": quick_score >= 2 or abs(daily_change) > 3 or volume_ratio > 2
                })

                time.sleep(0.2)  # Rate limit

            except Exception:
                continue

        return sorted(results, key=lambda x: (x.get('worth_deep_scan', False), x.get('quick_score', 0)), reverse=True)


# ============================================
# STREAMLIT INTEGRATION
# ============================================

@st.cache_resource
def get_oracle_scanner() -> OracleScanner:
    """Get or create Oracle scanner instance."""
    return OracleScanner()


def render_ai_guidance_tab():
    """Render the AI Guidance tab with Oracle recommendations."""
    st.header("AI Guidance")
    st.caption("Oracle's 15-Factor Analysis Engine")

    scanner = get_oracle_scanner()

    # Last scan info
    if 'oracle_scan_time' in st.session_state:
        st.caption(f"Last scan: {st.session_state['oracle_scan_time']}")

    # Scan controls
    col1, col2, col3 = st.columns([3, 1, 1])

    with col1:
        # Ticker input
        default_tickers = "NVDA, AAPL, MSFT, GOOGL, META, AMD, PLTR, TSLA"
        tickers_input = st.text_input(
            "Tickers to Scan",
            value=default_tickers,
            placeholder="Enter comma-separated tickers",
            key="ai_scan_tickers"
        )

    with col2:
        scan_btn = st.button("Scan Now", type="primary", width='stretch')

    with col3:
        # Clear results button to re-enable auto-refresh
        if 'oracle_results' in st.session_state and st.session_state['oracle_results']:
            if st.button("Clear Results", width='stretch'):
                st.session_state['oracle_results'] = None
                st.session_state['oracle_scan_time'] = None
                st.session_state['scan_requested'] = False
                st.rerun()

    # TWO-PHASE SCAN APPROACH:
    # Phase 1: Button clicked -> set scan_requested flag and rerun
    # Phase 2: On rerun (with autorefresh disabled), perform the actual scan
    if scan_btn:
        tickers = [t.strip().upper()
                   for t in tickers_input.split(",") if t.strip()]

        if not tickers:
            st.error("Please enter at least one ticker.")
        else:
            # Store tickers and set scan_requested flag
            st.session_state['scan_requested'] = True
            st.session_state['scan_tickers'] = tickers
            st.rerun()  # Rerun so autorefresh is disabled on next render

    # Phase 2: If scan was requested, perform it now (autorefresh is already disabled)
    if st.session_state.get('scan_requested') and st.session_state.get('scan_tickers'):
        tickers = st.session_state['scan_tickers']

        # Set scanning flags
        st.session_state['oracle_scanning'] = True
        st.session_state['scan_in_progress'] = True

        progress_bar = st.progress(0, text="Scanning with Oracle...")

        def update_progress(pct):
            progress_bar.progress(
                pct, text=f"Analyzing... {int(pct*100)}%")

        try:
            results = scanner.scan_watchlist(
                tickers, progress_callback=update_progress)
            progress_bar.empty()

            if results:
                st.session_state['oracle_results'] = results
                st.session_state['oracle_scan_time'] = datetime.now().strftime(
                    '%Y-%m-%d %H:%M:%S')
                st.success(f"Scan complete! Analyzed {len(results)} stocks.")
            else:
                st.warning("No results found. Check your tickers.")
        finally:
            # Clear ALL scanning-related flags
            st.session_state['oracle_scanning'] = False
            st.session_state['scan_in_progress'] = False
            st.session_state['scan_requested'] = False
            st.session_state['scan_tickers'] = None

    # Display results
    if 'oracle_results' in st.session_state and st.session_state['oracle_results']:
        results = st.session_state['oracle_results']

        st.divider()

        # Top Picks
        st.subheader("Oracle's Top Picks")

        strong_buys = [r for r in results if r.get('verdict') == 'Strong Buy']
        buys = [r for r in results if r.get('verdict') == 'Buy']

        if strong_buys or buys:
            top_picks = (strong_buys + buys)[:3]

            for pick in top_picks:
                verdict_color = "green" if "Buy" in pick.get(
                    'verdict', '') else "orange"

                with st.container():
                    col1, col2, col3 = st.columns([2, 1, 1])

                    with col1:
                        st.markdown(f"### {pick['ticker']}")
                        st.caption(f"{pick.get('sector', 'N/A')}")

                    with col2:
                        st.metric(
                            "Price", f"${pick.get('current_price', 0):.2f}")

                    with col3:
                        # DYNAMIC: Show score out of actual max (not fixed 12)
                        max_score = pick.get('max_score', 12)
                        score_pct = pick.get('score_pct', 0)
                        st.metric(
                            "Oracle Score",
                            f"{score_pct:.0f}%",
                            delta=pick.get('verdict')
                        )
                        st.caption(
                            f"{pick.get('score', 0):.1f}/{max_score:.1f} ({pick.get('available_factors', 15)}/{pick.get('total_factors', 15)} factors)")

                    # Reasons
                    if pick.get('reasons'):
                        st.write("**Key Reasons:**")
                        for reason in pick['reasons'][:3]:
                            st.write(f"  {reason}")

                    st.divider()
        else:
            st.info("No strong buy signals found. Market may be challenging.")

        # Full Results Table
        st.subheader("Full Scan Results")

        # DYNAMIC: Show percentage score and available factors
        df = pd.DataFrame([{
            "Ticker": r['ticker'],
            "Score %": f"{r.get('score_pct', 0):.0f}%",
            "Score": f"{r.get('score', 0):.1f}/{r.get('max_score', 12):.1f}",
            "Factors": f"{r.get('available_factors', 15)}/{r.get('total_factors', 15)}",
            "Verdict": r.get('verdict', 'N/A'),
            "Price": f"${r.get('current_price', 0):.2f}",
            "Sector": r.get('sector', 'N/A')
        } for r in results])

        st.dataframe(df, hide_index=True, width='stretch')

        # Detailed Factor Breakdown
        st.divider()
        st.subheader("Factor Breakdown")

        selected_ticker = st.selectbox(
            "Select ticker for detailed analysis",
            options=[r['ticker'] for r in results]
        )

        if selected_ticker:
            selected = next(
                (r for r in results if r['ticker'] == selected_ticker), None)

            if selected and selected.get('factors'):
                factors = selected['factors']

                # Show score summary with dynamic max
                st.caption(
                    f"Score: {selected.get('score', 0):.1f} / {selected.get('max_score', 12):.1f} "
                    f"({selected.get('available_factors', 15)}/{selected.get('total_factors', 15)} factors with data)"
                )

                # Create factor display with has_data status
                factor_data = []
                for factor_name, factor_info in factors.items():
                    has_data = factor_info.get('has_data', True)
                    max_pts = factor_info.get('max', 1.0)
                    factor_data.append({
                        "Factor": factor_name.replace("_", " ").title(),
                        "Value": str(factor_info.get('value', 'N/A')),
                        "Score": f"{factor_info.get('score', 0):.2f}/{max_pts:.2f}" if has_data else "N/A",
                        "Status": "✓" if has_data else "—",
                        "Detail": factor_info.get('detail', '')
                    })

                factor_df = pd.DataFrame(factor_data)
                st.dataframe(factor_df, hide_index=True, width='stretch')

                # AI Analysis Button
                st.divider()
                st.subheader("🤖 AI Investment Thesis")
                if st.button(f"Generate AI Report for {selected_ticker}", type="primary"):
                    with st.spinner(f"Consulting Gemini about {selected_ticker}..."):
                        analysis = scanner.get_ai_analysis(
                            selected_ticker, selected)
                        if analysis:
                            st.markdown(analysis)
                            # Expanders for details
                            with st.expander("View Prompt Data"):
                                st.json(selected)
                        else:
                            st.error(
                                "AI Analysis failed. Check API key in Settings.")
