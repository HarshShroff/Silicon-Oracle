"""
Silicon Oracle - Enhanced 15-Factor Oracle Scoring System
Complete implementation with all factors from ai_scanner.py
"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np

from flask_app.services.oracle_service import OracleService as BaseOracle

logger = logging.getLogger(__name__)

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


class EnhancedOracleService(BaseOracle):
    """
    Enhanced 15-Factor Oracle Scoring System.
    Inherits from base Oracle and adds missing factors.
    """

    def __init__(self, config: Optional[Dict[str, str]] = None):
        super().__init__(config)
        self.sector_momentum: Dict[str, Any] = {}
        self.market_movers: List[Dict[str, Any]] = []

    def calculate_enhanced_oracle_score(self, ticker: str) -> Dict[str, Any]:
        """
        Calculate comprehensive 15-factor Oracle score.
        """
        # Get base score (12 factors from parent)
        result = super().calculate_oracle_score(ticker)

        # Add enhanced factors 13-15
        score = result["score"]
        max_score = result["max_score"]
        factors = result.get("factors", [])

        # Get additional data
        stock_service = self.stock_service
        hist_data = stock_service.get_historical_data(ticker, period="2y", interval="1d")

        if hist_data is None or hist_data.empty:
            # Return base result if no historical data
            return result

        # FACTOR 13: Sector Momentum (Max: 0.5)
        sector_score = self._calculate_sector_momentum(hist_data, ticker)
        if sector_score is not None:
            score += sector_score["points"]
            max_score += 0.5
            factors.append(
                {
                    "name": "Sector Momentum",
                    "signal": sector_score["signal"],
                    "detail": sector_score["detail"],
                    "points": sector_score["points"],
                    "max_points": 0.5,
                    "has_data": True,
                }
            )

        # FACTOR 14: Beta/Volatility (Max: 0.5)
        beta_score = self._calculate_beta_score(hist_data, ticker)
        if beta_score is not None:
            score += beta_score["points"]
            max_score += 0.5
            factors.append(
                {
                    "name": "Beta (Volatility)",
                    "signal": beta_score["signal"],
                    "detail": beta_score["detail"],
                    "points": beta_score["points"],
                    "max_points": 0.5,
                    "has_data": True,
                }
            )

        # FACTOR 15: MACD Signal (Max: 0.5)
        macd_score = self._calculate_macd_signal(hist_data)
        if macd_score is not None:
            score += macd_score["points"]
            max_score += 0.5
            factors.append(
                {
                    "name": "MACD Signal",
                    "signal": macd_score["signal"],
                    "detail": macd_score["detail"],
                    "points": macd_score["points"],
                    "max_points": 0.5,
                    "has_data": True,
                }
            )

        # Update result with enhanced factors
        result.update(
            {
                "score": score,
                "max_score": max_score,
                "confidence": (score / max_score * 100) if max_score > 0 else 0,
                "factors": factors,
                "available_factors": sum(1 for f in factors if f.get("has_data", False)),
                "total_factors": len(factors),
            }
        )

        return result

    def _calculate_sector_momentum(self, hist_data, ticker: str) -> Optional[Dict[str, Any]]:
        """Calculate sector momentum by comparing stock to its sector ETF."""
        try:
            # Get company info to determine sector
            company = self.stock_service.get_company_info(ticker)
            if not company:
                return None

            sector = company.get("sector", "Unknown")
            sector_etf = SECTOR_ETFS.get(sector)

            if not sector_etf:
                return {
                    "signal": "N/A",
                    "detail": f"Unknown sector: {sector}",
                    "points": 0,
                }

            # Get sector ETF data
            etf_data = self.stock_service.get_historical_data(
                sector_etf, period="1y", interval="1d"
            )
            if etf_data is None or etf_data.empty:
                return {
                    "signal": "N/A",
                    "detail": f"No sector ETF data for {sector_etf}",
                    "points": 0,
                }

            # Calculate 3-month returns
            stock_3m = self._calculate_period_return(hist_data, 63)  # ~3 months
            sector_3m = self._calculate_period_return(etf_data, 63)

            if stock_3m is None or sector_3m is None:
                return None

            # Compare stock to sector
            outperformance = stock_3m - sector_3m

            if outperformance >= 5:  # 5% better than sector
                return {
                    "signal": "Bullish",
                    "detail": f"Outperforming {sector} by {outperformance:+.1f}%",
                    "points": 0.5,
                }
            elif outperformance >= 2:  # 2-5% better
                return {
                    "signal": "Bullish",
                    "detail": f"Slightly ahead of {sector}",
                    "points": 0.35,
                }
            elif outperformance >= -2:  # Within 2%
                return {
                    "signal": "Neutral",
                    "detail": f"Performing in line with {sector}",
                    "points": 0.25,
                }
            else:  # Underperforming
                return {
                    "signal": "Bearish",
                    "detail": f"Underperforming {sector} by {outperformance:+.1f}%",
                    "points": 0,
                }

        except Exception as e:
            logger.error(f"Error calculating sector momentum for {ticker}: {e}")
            return None

    def _calculate_beta_score(self, hist_data, ticker: str) -> Optional[Dict[str, Any]]:
        """Calculate beta score based on volatility relative to market."""
        try:
            # Get SPY data for market
            spy_data = self.stock_service.get_historical_data("SPY", period="1y", interval="1d")
            if spy_data is None or spy_data.empty:
                return None

            # Align data periods
            min_len = min(len(hist_data), len(spy_data))
            if min_len < 50:  # Need at least 50 days
                return None

            stock_returns = hist_data["Close"].pct_change().iloc[-min_len:].dropna()
            spy_returns = spy_data["Close"].pct_change().iloc[-min_len:].dropna()

            # Calculate beta
            if len(stock_returns) == 0 or len(spy_returns) == 0:
                return None

            # Simple beta calculation (covariance / variance)
            beta = stock_returns.cov(spy_returns) / spy_returns.var()

            # Calculate stock volatility
            stock_vol = stock_returns.std() * np.sqrt(252)  # Annualized

            # Score based on beta and volatility
            if beta is None or np.isnan(beta):
                return None

            # Ideal beta range is 0.8-1.2 for most stocks
            if 0.8 <= beta <= 1.2 and stock_vol <= 0.4:  # Moderate beta and volatility
                return {
                    "signal": "Bullish",
                    "detail": f"Beta {beta:.2f}, moderate volatility",
                    "points": 0.5,
                }
            elif beta > 1.5:  # High beta
                if stock_vol > 0.5:  # High volatility too
                    return {
                        "signal": "Bearish",
                        "detail": f"High beta ({beta:.2f}) and volatility",
                        "points": 0,
                    }
                else:
                    return {
                        "signal": "Neutral",
                        "detail": f"High beta ({beta:.2f}) but manageable",
                        "points": 0.25,
                    }
            elif beta < 0.5:  # Low beta
                return {
                    "signal": "Neutral",
                    "detail": f"Low beta ({beta:.2f}) - defensive stock",
                    "points": 0.25,
                }
            else:
                return {
                    "signal": "Neutral",
                    "detail": f"Beta {beta:.2f} - normal range",
                    "points": 0.35,
                }

        except Exception as e:
            logger.error(f"Error calculating beta score for {ticker}: {e}")
            return None

    def _calculate_macd_signal(self, hist_data) -> Optional[Dict[str, Any]]:
        """Calculate MACD signal."""
        try:
            if len(hist_data) < 26:  # Need at least 26 periods for MACD
                return None

            close_prices = hist_data["Close"]

            # Calculate MACD
            ema12 = close_prices.ewm(span=12).mean()
            ema26 = close_prices.ewm(span=26).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9).mean()
            histogram = macd_line - signal_line

            # Get latest values
            current_macd = macd_line.iloc[-1]
            current_signal = signal_line.iloc[-1]
            current_hist = histogram.iloc[-1]

            # Previous values for crossover detection
            prev_macd = macd_line.iloc[-2]
            prev_signal = signal_line.iloc[-2]

            # Determine signal
            if current_macd > current_signal:
                if prev_macd <= prev_signal:  # Bullish crossover
                    return {
                        "signal": "Bullish",
                        "detail": "MACD bullish crossover detected",
                        "points": 0.5,
                    }
                elif current_hist > 0:  # Positive histogram
                    return {
                        "signal": "Bullish",
                        "detail": "MACD above signal line",
                        "points": 0.35,
                    }
                else:
                    return {
                        "signal": "Neutral",
                        "detail": "MACD slightly above signal",
                        "points": 0.25,
                    }
            else:
                if prev_macd >= prev_signal:  # Bearish crossover
                    return {
                        "signal": "Bearish",
                        "detail": "MACD bearish crossover detected",
                        "points": 0,
                    }
                elif current_hist < 0:  # Negative histogram
                    return {
                        "signal": "Bearish",
                        "detail": "MACD below signal line",
                        "points": 0.1,
                    }
                else:
                    return {
                        "signal": "Neutral",
                        "detail": "MACD slightly below signal",
                        "points": 0.2,
                    }

        except Exception as e:
            logger.error(f"Error calculating MACD signal: {e}")
            return None

    def _calculate_period_return(self, data, periods: int) -> Optional[float]:
        """Calculate return over specified number of periods."""
        try:
            if len(data) < periods:
                return None

            start_price = data["Close"].iloc[-periods]
            end_price = data["Close"].iloc[-1]

            if start_price <= 0:
                return None

            return ((end_price - start_price) / start_price) * 100
        except Exception:
            return None

    def detect_volume_spikes(self, tickers: List[str]) -> List[Dict[str, Any]]:
        """Detect unusual volume spikes for given tickers."""
        spikes = []

        for ticker in tickers:
            try:
                data = self.stock_service.get_historical_data(ticker, period="3m", interval="1d")
                if data is None or data.empty:
                    continue

                # Calculate average volume (excluding last 5 days)
                if len(data) < 30:  # Need at least 30 days
                    continue

                recent_vol = data["Volume"].iloc[-1]  # Most recent
                avg_vol = data["Volume"].iloc[:-5].mean()  # Average excluding recent

                if avg_vol > 0:
                    vol_ratio = recent_vol / avg_vol

                    if vol_ratio >= 2.0:  # 2x average volume
                        price_change = (
                            (data["Close"].iloc[-1] - data["Close"].iloc[-2])
                            / data["Close"].iloc[-2]
                        ) * 100

                        spikes.append(
                            {
                                "ticker": ticker,
                                "volume_ratio": vol_ratio,
                                "current_volume": recent_vol,
                                "avg_volume": avg_vol,
                                "price_change": price_change,
                                "price": data["Close"].iloc[-1],
                            }
                        )

            except Exception as e:
                logger.error(f"Error detecting volume spike for {ticker}: {e}")
                continue

        # Sort by volume ratio (highest first)
        spikes.sort(key=lambda x: x["volume_ratio"], reverse=True)
        return spikes

    def get_relative_strength(self, tickers: List[str]) -> List[Dict[str, Any]]:
        """Calculate relative strength vs SPY for tickers."""
        results: List[Dict[str, Any]] = []
        spy_data = self.stock_service.get_historical_data("SPY", period="3m", interval="1d")

        if spy_data is None or spy_data.empty:
            return results

        spy_return = self._calculate_period_return(spy_data, 63)  # 3 months

        for ticker in tickers:
            try:
                data = self.stock_service.get_historical_data(ticker, period="3m", interval="1d")
                if data is None or data.empty:
                    continue

                ticker_return = self._calculate_period_return(data, 63)
                if ticker_return is None:
                    continue

                relative_strength = ticker_return - spy_return if spy_return else ticker_return

                results.append(
                    {
                        "ticker": ticker,
                        "return_3m": ticker_return,
                        "spy_return": spy_return,
                        "relative_strength": relative_strength,
                        "price": data["Close"].iloc[-1],
                    }
                )

            except Exception as e:
                logger.error(f"Error calculating relative strength for {ticker}: {e}")
                continue

        # Sort by relative strength
        results.sort(key=lambda x: x["relative_strength"], reverse=True)
        return results
