"""
Silicon Oracle - Oracle Scoring Service
15-Factor Multi-Dimensional Stock Analysis Engine
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask_app.services.stock_service import StockService

logger = logging.getLogger(__name__)


class OracleService:
    """
    The Oracle - A comprehensive multi-factor scoring system.
    Evaluates stocks across 15 dimensions for a score from 0-12 points.
    """

    def __init__(self, config: Optional[Dict[str, str]] = None):
        self.stock_service = StockService(config)
        self.spy_data: Optional[Dict[str, Any]] = None  # Cache SPY data for market context

    def _get_market_context(self) -> Dict[str, Any]:
        """Get SPY data for market context."""
        if self.spy_data is None:
            self.spy_data = self.stock_service.get_technical_indicators("SPY")
        return self.spy_data or {}

    def calculate_oracle_score(self, ticker: str) -> Dict[str, Any]:
        """
        Calculate comprehensive Oracle score for a ticker.
        Returns score, verdict, factors breakdown, and confidence.
        """
        # Get all required data
        data = self.stock_service.get_complete_data(ticker)
        spy_data = self._get_market_context()

        # Dynamic scoring: track score and max possible
        score = 0.0
        max_score = 0.0
        factors = []

        def add_factor(
            name: str,
            signal: str,
            detail: str,
            points: float,
            max_points: float,
            has_data: bool = True,
        ):
            """Add a factor to the scoring."""
            nonlocal score, max_score

            factors.append(
                {
                    "name": name,
                    "signal": signal,
                    "detail": detail,
                    "points": points if has_data else 0,
                    "max_points": max_points if has_data else 0,
                    "has_data": has_data,
                }
            )

            if has_data:
                score += points
                max_score += max_points

        # Extract data components
        quote = data.get("quote") or {}
        company = data.get("company") or {}
        technicals = data.get("technicals") or {}
        recommendations = data.get("recommendations") or []
        price_targets = data.get("price_targets") or {}
        insiders = data.get("insiders") or []
        earnings = data.get("earnings")
        news = data.get("news") or []

        current_price = quote.get("current") or technicals.get("price", 0)
        sma_50 = technicals.get("sma_50")
        rsi = technicals.get("rsi")

        # ============================================
        # FACTOR 1: TECHNICAL TREND (Max: 1.0)
        # ============================================
        if sma_50 and current_price:
            if current_price > sma_50:
                add_factor("Trend", "Bullish", "Price above SMA50 (Uptrend)", 1.0, 1.0)
            else:
                add_factor("Trend", "Bearish", "Price below SMA50 (Downtrend)", 0.0, 1.0)
        else:
            add_factor("Trend", "N/A", "Insufficient technical data", 0, 0, has_data=False)

        # ============================================
        # FACTOR 2: MOMENTUM - RSI (Max: 1.0)
        # ============================================
        if rsi is not None:
            if 30 <= rsi <= 70:
                add_factor("Momentum", "Bullish", f"RSI {rsi:.0f} - Healthy range", 1.0, 1.0)
            elif rsi < 30:
                add_factor("Momentum", "Neutral", f"RSI {rsi:.0f} - Oversold", 0.5, 1.0)
            else:
                add_factor("Momentum", "Bearish", f"RSI {rsi:.0f} - Overbought", 0.0, 1.0)
        else:
            add_factor("Momentum", "N/A", "No RSI data", 0, 0, has_data=False)

        # ============================================
        # FACTOR 3: MARKET CONTEXT (Max: 1.0)
        # ============================================
        spy_price = spy_data.get("price", 0)
        spy_sma = spy_data.get("sma_50", 0)

        if spy_price and spy_sma:
            if spy_price > spy_sma:
                add_factor("Market", "Bullish", "S&P 500 in uptrend (Risk-On)", 1.0, 1.0)
            else:
                add_factor("Market", "Bearish", "S&P 500 weak (Risk-Off)", 0.0, 1.0)
        else:
            add_factor("Market", "N/A", "No market data", 0, 0, has_data=False)

        # ============================================
        # FACTOR 4: ANALYST CONSENSUS (Max: 1.0)
        # ============================================
        if recommendations and len(recommendations) > 0:
            latest = recommendations[0]
            strong_buy = latest.get("strongBuy", 0)
            buy = latest.get("buy", 0)
            total = sum(
                [latest.get(k, 0) for k in ["strongBuy", "buy", "hold", "sell", "strongSell"]]
            )

            if total > 0:
                bullish_pct = ((strong_buy + buy) / total) * 100

                if bullish_pct >= 60:
                    add_factor("Analysts", "Bullish", f"{bullish_pct:.0f}% Bullish", 1.0, 1.0)
                elif bullish_pct >= 40:
                    add_factor("Analysts", "Neutral", f"{bullish_pct:.0f}% Bullish", 0.5, 1.0)
                else:
                    add_factor("Analysts", "Bearish", f"Only {bullish_pct:.0f}% Bullish", 0.0, 1.0)
            else:
                add_factor("Analysts", "N/A", "No analyst coverage", 0, 0, has_data=False)
        else:
            add_factor("Analysts", "N/A", "No analyst data", 0, 0, has_data=False)

        # ============================================
        # FACTOR 5: INSIDER ACTIVITY (Max: 1.0)
        # ============================================
        if insiders and len(insiders) > 0:
            buy_value = sum(
                [
                    t.get("share", 0) * t.get("transactionPrice", 0)
                    for t in insiders
                    if t.get("change", 0) > 0
                ]
            )
            sell_value = sum(
                [
                    abs(t.get("share", 0)) * t.get("transactionPrice", 0)
                    for t in insiders
                    if t.get("change", 0) < 0
                ]
            )

            if buy_value > sell_value:
                add_factor("Insiders", "Bullish", "Net insider buying detected", 1.0, 1.0)
            elif sell_value > buy_value * 2:
                add_factor("Insiders", "Bearish", "Heavy insider selling", 0.0, 1.0)
            else:
                add_factor("Insiders", "Neutral", "Mixed insider activity", 0.5, 1.0)
        else:
            add_factor("Insiders", "N/A", "No insider data (ETF/Fund)", 0, 0, has_data=False)

        # ============================================
        # FACTOR 6: PRICE TARGET UPSIDE (Max: 1.0)
        # ============================================
        target_mean = price_targets.get("target_mean") or company.get("target_price")

        if current_price and target_mean and current_price > 0 and target_mean > 0:
            upside_pct = ((target_mean - current_price) / current_price) * 100

            if upside_pct >= 15:
                add_factor("Target", "Bullish", f"{upside_pct:+.1f}% upside to target", 1.0, 1.0)
            elif upside_pct >= 5:
                add_factor("Target", "Neutral", f"{upside_pct:+.1f}% modest upside", 0.5, 1.0)
            elif upside_pct >= -5:
                add_factor("Target", "Neutral", f"{upside_pct:+.1f}% near target", 0.5, 1.0)
            else:
                add_factor("Target", "Bearish", f"{upside_pct:.1f}% downside risk", 0.0, 1.0)
        else:
            add_factor("Target", "N/A", "No price target data", 0, 0, has_data=False)

        # ============================================
        # FACTOR 7: VALUATION - PEG/PE (Max: 1.0)
        # ============================================
        peg = company.get("peg_ratio")
        pe = company.get("pe_ratio")

        if peg and peg > 0:
            if peg < 1:
                add_factor("Valuation", "Bullish", f"PEG {peg:.2f} - Undervalued", 1.0, 1.0)
            elif peg < 2:
                add_factor("Valuation", "Neutral", f"PEG {peg:.2f} - Fair value", 0.5, 1.0)
            else:
                add_factor("Valuation", "Bearish", f"PEG {peg:.2f} - Expensive", 0.0, 1.0)
        elif pe and pe > 0:
            if pe < 15:
                add_factor("Valuation", "Bullish", f"P/E {pe:.1f} - Low", 0.75, 1.0)
            elif pe < 25:
                add_factor("Valuation", "Neutral", f"P/E {pe:.1f} - Fair", 0.5, 1.0)
            else:
                add_factor("Valuation", "Neutral", f"P/E {pe:.1f} - Growth stock", 0.25, 1.0)
        else:
            add_factor("Valuation", "N/A", "No valuation data", 0, 0, has_data=False)

        # ============================================
        # FACTOR 8: EARNINGS PROXIMITY (Max: 0.5)
        # ============================================
        if earnings and earnings.get("date"):
            try:
                earn_date = datetime.strptime(earnings["date"], "%Y-%m-%d")
                days_until = (earn_date - datetime.now()).days

                if 7 <= days_until <= 30:
                    add_factor(
                        "Earnings", "Caution", f"Earnings in {days_until}d (Catalyst)", 0.5, 0.5
                    )
                elif 0 <= days_until < 7:
                    add_factor(
                        "Earnings",
                        "Caution",
                        f"Earnings in {days_until}d (High Volatility)",
                        0.0,
                        0.5,
                    )
                elif days_until > 30:
                    add_factor("Earnings", "Neutral", f"Earnings in {days_until}d", 0.4, 0.5)
                else:
                    add_factor("Earnings", "Clear", "Earnings passed", 0.25, 0.5)
            except Exception:
                add_factor("Earnings", "N/A", "Date parse error", 0, 0, has_data=False)
        else:
            add_factor("Earnings", "N/A", "No earnings data (ETF)", 0, 0, has_data=False)

        # ============================================
        # FACTOR 9: NEWS SENTIMENT (Max: 1.0)
        # ============================================
        if news and len(news) >= 3:
            bullish_words = [
                "surge",
                "gain",
                "beat",
                "upgrade",
                "bullish",
                "buy",
                "strong",
                "growth",
                "rally",
            ]
            bearish_words = [
                "drop",
                "fall",
                "miss",
                "downgrade",
                "bearish",
                "sell",
                "weak",
                "loss",
                "decline",
            ]

            pos_count = 0
            neg_count = 0
            for item in news[:5]:
                text = (item.get("headline", "") + " " + item.get("summary", "")).lower()
                if any(w in text for w in bullish_words):
                    pos_count += 1
                if any(w in text for w in bearish_words):
                    neg_count += 1

            if pos_count > neg_count:
                add_factor("News", "Bullish", "Positive media coverage", 1.0, 1.0)
            elif neg_count > pos_count:
                add_factor("News", "Bearish", "Negative media coverage", 0.0, 1.0)
            else:
                add_factor("News", "Neutral", "Mixed media sentiment", 0.5, 1.0)
        else:
            add_factor("News", "N/A", "Insufficient news data", 0, 0, has_data=False)

        # ============================================
        # FACTOR 10: DIVIDEND YIELD (Max: 0.5)
        # ============================================
        div_yield = company.get("dividend_yield", 0)
        if div_yield and div_yield > 0:
            div_pct = div_yield * 100 if div_yield < 1 else div_yield
            if div_pct >= 3:
                add_factor("Dividend", "Bullish", f"{div_pct:.2f}% yield (Income)", 0.5, 0.5)
            elif div_pct >= 1:
                add_factor("Dividend", "Neutral", f"{div_pct:.2f}% yield", 0.25, 0.5)
            else:
                add_factor("Dividend", "Neutral", f"{div_pct:.2f}% yield (Low)", 0.1, 0.5)
        else:
            add_factor("Dividend", "N/A", "No dividend (Growth)", 0, 0, has_data=False)

        # ============================================
        # FACTOR 11: VOLATILITY (Max: 0.5)
        # ============================================
        volatility = technicals.get("volatility")
        if volatility is not None:
            if volatility < 20:
                add_factor("Volatility", "Bullish", f"{volatility:.1f}% - Low risk", 0.5, 0.5)
            elif volatility < 40:
                add_factor("Volatility", "Neutral", f"{volatility:.1f}% - Moderate", 0.25, 0.5)
            else:
                add_factor("Volatility", "Bearish", f"{volatility:.1f}% - High risk", 0.0, 0.5)
        else:
            add_factor("Volatility", "N/A", "No volatility data", 0, 0, has_data=False)

        # ============================================
        # FACTOR 12: 52-WEEK POSITION (Max: 0.5)
        # ============================================
        year_high = company.get("year_high", 0)
        year_low = company.get("year_low", 0)

        if current_price and year_high > year_low > 0:
            position = (current_price - year_low) / (year_high - year_low)
            if position < 0.3:
                add_factor("52W Range", "Bullish", "Near 52-week low", 0.5, 0.5)
            elif position > 0.8:
                add_factor("52W Range", "Caution", "Near 52-week high", 0.0, 0.5)
            else:
                add_factor("52W Range", "Neutral", "Mid-range", 0.25, 0.5)
        else:
            add_factor("52W Range", "N/A", "No range data", 0, 0, has_data=False)

        # ============================================
        # CALCULATE FINAL VERDICT
        # ============================================
        confidence = (score / max_score * 100) if max_score > 0 else 50
        available_factors = sum(1 for f in factors if f["has_data"])

        if confidence >= 75:
            verdict = "STRONG_BUY"
            verdict_text = "Strong Buy"
            verdict_detail = "High conviction - Multiple factors aligning"
        elif confidence >= 55:
            verdict = "BUY"
            verdict_text = "Buy / Accumulate"
            verdict_detail = "Positive outlook - Good risk/reward"
        elif confidence >= 40:
            verdict = "HOLD"
            verdict_text = "Hold / Watch"
            verdict_detail = "Mixed signals - Wait for clarity"
        elif confidence >= 25:
            verdict = "AVOID"
            verdict_text = "Avoid"
            verdict_detail = "Negative factors dominate"
        else:
            verdict = "STRONG_SELL"
            verdict_text = "Strong Sell"
            verdict_detail = "Multiple red flags detected"

        return {
            "ticker": ticker,
            "timestamp": datetime.now().isoformat(),
            "score": round(score, 2),
            "max_score": round(max_score, 2),
            "confidence": round(confidence, 1),
            "verdict": verdict,
            "verdict_text": verdict_text,
            "verdict_detail": verdict_detail,
            "factors": factors,
            "available_factors": available_factors,
            "total_factors": len(factors),
            "quote": quote,
            "company": company,
            "rsi": rsi,
            "volume": technicals.get("volume", 0),
        }

    def scan_watchlist(self, tickers: List[str]) -> List[Dict[str, Any]]:
        """Scan multiple tickers and rank by Oracle score."""
        results = []

        for ticker in tickers:
            try:
                result = self.calculate_oracle_score(ticker)
                results.append(result)
            except Exception as e:
                logger.warning(f"Failed to scan {ticker}: {e}")
                results.append(
                    {"ticker": ticker, "error": str(e), "confidence": 0, "verdict": "ERROR"}
                )

        # Sort by confidence descending
        results.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        return results
