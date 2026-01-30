"""
Silicon Oracle - Scanner Service
Multi-Ticker Market Analysis Engine
"""

import logging
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask_app.services.stock_service import StockService

logger = logging.getLogger(__name__)

# Pre-built watchlists
WATCHLISTS = {
    "AI/Tech": ["NVDA", "AMD", "MSFT", "GOOGL", "META", "AVGO", "TSM"],
    "Energy": ["VST", "URA", "XLE", "NEE", "CEG", "CCJ"],
    "Dividend": ["SCHD", "VYM", "O", "JEPI", "HDV"],
    "Speculative": ["PLTR", "SOFI", "COIN", "MSTR", "HOOD"],
    "ETFs": ["SPY", "QQQ", "IWM", "DIA", "VTI"],
    "Magnificent 7": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"],
    "Custom": []
}


class ScannerService:
    """Service for scanning multiple stocks."""

    def __init__(self, config: Dict[str, str] = None):
        self.stock_service = StockService(config)
        self._spy_data = None

    def _get_spy_context(self) -> Dict[str, Any]:
        """Get SPY data for market context."""
        if self._spy_data is None:
            self._spy_data = self.stock_service.get_technical_indicators('SPY')
        return self._spy_data or {}

    def scan_ticker(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Scan a single ticker."""
        try:
            indicators = self.stock_service.get_technical_indicators(ticker)
            if not indicators:
                return None

            spy_data = self._get_spy_context()
            score, signal, reasons = self._calculate_quick_score(indicators, spy_data)

            return {
                'ticker': ticker,
                'price': indicators.get('price', 0),
                'rsi': indicators.get('rsi', 50),
                'daily_change': indicators.get('daily_change', 0),
                'perf_1m': indicators.get('perf_1m', 0),
                'volatility': indicators.get('volatility', 0),
                'volume': indicators.get('volume', 0),
                'volume_ratio': indicators.get('volume_ratio', 1),
                'score': score,
                'signal': signal,
                'reasons': reasons
            }
        except Exception as e:
            logger.warning(f"Error scanning {ticker}: {e}")
            return None

    def _calculate_quick_score(self, indicators: Dict, spy_data: Dict) -> tuple:
        """Calculate quick Oracle score (0-3)."""
        score = 0
        reasons = []

        # 1. Trend
        if indicators.get('sma_50') and indicators.get('price'):
            if indicators['price'] > indicators['sma_50']:
                score += 1
                reasons.append("Uptrend (Price > SMA50)")
            else:
                reasons.append("Downtrend")

        # 2. RSI
        rsi = indicators.get('rsi', 50)
        if rsi < 70:
            score += 1
            reasons.append(f"RSI {rsi:.0f} - Not overbought")
        else:
            reasons.append(f"RSI {rsi:.0f} - Overbought")

        # 3. Market
        if spy_data.get('price') and spy_data.get('sma_50'):
            if spy_data['price'] > spy_data['sma_50']:
                score += 1
                reasons.append("Market bullish")
            else:
                reasons.append("Market weak")

        signal = "BUY" if score == 3 else ("WATCH" if score == 2 else "AVOID")
        return score, signal, reasons

    def scan_watchlist(self, tickers: List[str], max_workers: int = 5) -> List[Dict[str, Any]]:
        """Scan multiple tickers in parallel."""
        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.scan_ticker, t): t for t in tickers}

            for future in as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)

        results.sort(key=lambda x: (-x['score'], x['rsi']))
        return results

    def get_watchlist_names(self) -> List[str]:
        """Get available watchlist names."""
        return list(WATCHLISTS.keys())

    def get_watchlist_tickers(self, name: str) -> List[str]:
        """Get tickers for a watchlist."""
        return WATCHLISTS.get(name, [])

    def detect_volume_spikes(self, tickers: List[str], threshold: float = 1.5) -> List[Dict]:
        """Detect unusual volume."""
        spikes = []
        for ticker in tickers:
            indicators = self.stock_service.get_technical_indicators(ticker)
            if indicators and indicators.get('volume_ratio', 0) >= threshold:
                spikes.append({
                    'ticker': ticker,
                    'volume_ratio': indicators['volume_ratio'],
                    'price_change': indicators.get('daily_change', 0)
                })
        return sorted(spikes, key=lambda x: x['volume_ratio'], reverse=True)
