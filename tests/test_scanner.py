"""
Tests for flask_app/services/scanner_service.py
"""

from unittest.mock import patch

import pytest

from flask_app.services.scanner_service import ScannerService


@pytest.fixture
def svc():
    with patch("flask_app.services.scanner_service.StockService"):
        return ScannerService()


class TestWatchlists:
    def test_get_watchlist_names(self, svc):
        names = svc.get_watchlist_names()
        assert isinstance(names, list)
        assert len(names) > 0
        assert "AI/Tech" in names

    def test_get_watchlist_tickers_known(self, svc):
        tickers = svc.get_watchlist_tickers("AI/Tech")
        assert isinstance(tickers, list)
        assert "NVDA" in tickers

    def test_get_watchlist_tickers_unknown(self, svc):
        result = svc.get_watchlist_tickers("NonExistentList")
        assert result == []

    def test_all_predefined_watchlists_exist(self, svc):
        for name in ["AI/Tech", "Energy", "Dividend", "ETFs", "Magnificent 7"]:
            assert svc.get_watchlist_tickers(name) != [] or name == "Custom"


class TestCalculateQuickScore:
    """Test the pure scoring logic directly."""

    def _score(self, svc, indicators, spy_data=None):
        return svc._calculate_quick_score(indicators, spy_data or {})

    def test_score_3_all_conditions_met(self, svc):
        indicators = {"price": 110, "sma_50": 100, "rsi": 50}
        spy = {"price": 450, "sma_50": 440}
        score, signal, reasons = self._score(svc, indicators, spy)
        assert score == 3
        assert signal == "BUY"

    def test_score_2_no_spy_data(self, svc):
        """Without SPY data, max score is 2."""
        indicators = {"price": 110, "sma_50": 100, "rsi": 50}
        score, signal, reasons = self._score(svc, indicators, {})
        assert score == 2
        assert signal == "WATCH"

    def test_score_0_downtrend_overbought(self, svc):
        indicators = {"price": 90, "sma_50": 100, "rsi": 75}
        spy = {"price": 400, "sma_50": 450}
        score, signal, _ = self._score(svc, indicators, spy)
        assert score == 0
        assert signal == "AVOID"

    def test_trend_below_sma_reduces_score(self, svc):
        indicators = {"price": 90, "sma_50": 100, "rsi": 50}
        score, _, _ = self._score(svc, indicators, {})
        assert score == 1  # only RSI passes

    def test_overbought_rsi_reduces_score(self, svc):
        indicators = {"price": 110, "sma_50": 100, "rsi": 75}
        score, _, _ = self._score(svc, indicators, {})
        assert score == 1  # only trend passes

    def test_rsi_exactly_70_passes(self, svc):
        """RSI < 70 passes; RSI = 70 does NOT."""
        indicators = {"price": 110, "sma_50": 100, "rsi": 70}
        score_at_70, _, _ = self._score(svc, indicators)
        indicators["rsi"] = 69.9
        score_below_70, _, _ = self._score(svc, indicators)
        assert score_below_70 > score_at_70

    def test_missing_sma_skips_trend(self, svc):
        indicators = {"price": 110, "rsi": 50}  # no sma_50
        score, _, _ = self._score(svc, indicators, {})
        assert score == 1  # only RSI

    def test_bearish_spy_reduces_score(self, svc):
        indicators = {"price": 110, "sma_50": 100, "rsi": 50}
        spy = {"price": 400, "sma_50": 450}  # SPY below its SMA
        score, _, _ = self._score(svc, indicators, spy)
        assert score == 2  # trend + RSI but not market

    def test_score_1_signal_avoid(self, svc):
        indicators = {"price": 90, "sma_50": 100, "rsi": 50}
        score, signal, _ = self._score(svc, indicators, {})
        assert score == 1
        assert signal == "AVOID"


class TestScanTicker:
    def test_returns_none_when_no_indicators(self, svc):
        svc.stock_service.get_technical_indicators.return_value = None
        result = svc.scan_ticker("AAPL")
        assert result is None

    def test_returns_dict_with_correct_keys(self, svc):
        indicators = {
            "price": 150.0,
            "rsi": 55,
            "daily_change": 0.5,
            "perf_1m": 2.0,
            "volatility": 18.0,
            "volume": 50000000,
            "volume_ratio": 1.2,
            "sma_50": 140.0,
        }
        svc.stock_service.get_technical_indicators.return_value = indicators
        svc._spy_data = {"price": 450, "sma_50": 440}
        result = svc.scan_ticker("AAPL")
        assert result is not None
        for key in ["ticker", "price", "rsi", "score", "signal", "reasons"]:
            assert key in result
        assert result["ticker"] == "AAPL"

    def test_returns_none_on_exception(self, svc):
        svc.stock_service.get_technical_indicators.side_effect = Exception("network error")
        result = svc.scan_ticker("BADTICKER")
        assert result is None


class TestVolumeSpikes:
    def test_detects_spike_above_threshold(self, svc):
        svc.stock_service.get_technical_indicators.return_value = {
            "volume_ratio": 2.5,
            "daily_change": 3.0,
        }
        result = svc.detect_volume_spikes(["AAPL"], threshold=1.5)
        assert len(result) == 1
        assert result[0]["ticker"] == "AAPL"

    def test_skips_below_threshold(self, svc):
        svc.stock_service.get_technical_indicators.return_value = {
            "volume_ratio": 1.2,
            "daily_change": 0.5,
        }
        result = svc.detect_volume_spikes(["AAPL"], threshold=1.5)
        assert result == []

    def test_sorted_descending_by_ratio(self, svc):
        def mock_indicators(ticker):
            return {
                "AAPL": {"volume_ratio": 2.0, "daily_change": 1.0},
                "MSFT": {"volume_ratio": 3.5, "daily_change": 2.0},
            }.get(ticker)

        svc.stock_service.get_technical_indicators.side_effect = mock_indicators
        result = svc.detect_volume_spikes(["AAPL", "MSFT"], threshold=1.5)
        assert result[0]["ticker"] == "MSFT"
        assert result[1]["ticker"] == "AAPL"

    def test_skips_ticker_with_no_data(self, svc):
        svc.stock_service.get_technical_indicators.return_value = None
        result = svc.detect_volume_spikes(["AAPL"])
        assert result == []

    def test_empty_tickers_list(self, svc):
        result = svc.detect_volume_spikes([])
        assert result == []


class TestSpyContext:
    def test_spy_data_cached(self, svc):
        svc.stock_service.get_technical_indicators.return_value = {"price": 450}
        _ = svc._get_spy_context()
        _ = svc._get_spy_context()
        # Should only be called once
        assert svc.stock_service.get_technical_indicators.call_count == 1

    def test_spy_data_returns_empty_dict_on_none(self, svc):
        svc.stock_service.get_technical_indicators.return_value = None
        result = svc._get_spy_context()
        assert result == {}
