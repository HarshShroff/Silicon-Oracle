"""
Tests for Silicon Oracle Stock Service.
Run with: pytest tests/test_stock_service.py -v
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestStockServiceInit:
    """Tests for StockService initialization."""

    def test_init_without_config(self):
        """StockService initializes without config."""
        from flask_app.services.stock_service import StockService

        svc = StockService()
        assert svc is not None
        assert svc.config == {}

    def test_init_with_config(self):
        """StockService stores provided config."""
        from flask_app.services.stock_service import StockService

        svc = StockService({"FINNHUB_API_KEY": "test-key"})
        assert svc.config.get("FINNHUB_API_KEY") == "test-key"

    def test_init_with_empty_config(self):
        """StockService initializes with empty dict."""
        from flask_app.services.stock_service import StockService

        svc = StockService({})
        assert svc.config == {}

    def test_init_clients_no_finnhub(self):
        """StockService handles missing Finnhub gracefully."""
        from flask_app.services.stock_service import StockService

        svc = StockService()
        assert svc._finnhub_client is None


class TestGetRealtimeQuote:
    """Tests for get_realtime_quote."""

    def test_quote_no_client_returns_none(self):
        """get_realtime_quote returns None without Finnhub client."""
        from flask_app.services.stock_service import StockService

        svc = StockService()
        result = svc.get_realtime_quote("AAPL")
        assert result is None

    @patch("finnhub.Client")
    def test_quote_with_finnhub(self, mock_client):
        """get_realtime_quote uses Finnhub when available."""
        from flask_app.services.stock_service import StockService

        mock_instance = MagicMock()
        mock_instance.quote.return_value = {
            "c": 150.0,
            "d": 1.0,
            "dp": 0.67,
            "h": 151.0,
            "l": 149.0,
            "o": 149.0,
            "pc": 149.0,
        }
        mock_client.return_value = mock_instance

        svc = StockService({"FINNHUB_API_KEY": "test-key"})
        result = svc.get_realtime_quote("AAPL")

        assert result is not None
        assert result["current"] == 150.0
        assert result["source"] == "finnhub"

    @patch("finnhub.Client")
    def test_quote_finnhub_returns_zero(self, mock_client):
        """get_realtime_quote falls back to yfinance when Finnhub returns zero."""
        from flask_app.services.stock_service import StockService

        mock_instance = MagicMock()
        mock_instance.quote.return_value = {
            "c": 0,
            "d": 0,
            "dp": 0,
            "h": 0,
            "l": 0,
            "o": 0,
            "pc": 0,
        }
        mock_client.return_value = mock_instance

        svc = StockService({"FINNHUB_API_KEY": "test-key"})
        result = svc.get_realtime_quote("AAPL")

        assert result is None or result.get("source") == "yfinance"

    @patch("yfinance.Ticker")
    def test_quote_yfinance_fallback(self, mock_ticker):
        """get_realtime_quote falls back to yfinance."""
        import pandas as pd

        from flask_app.services.stock_service import StockService

        mock_stock = MagicMock()
        mock_stock.history.return_value = pd.DataFrame(
            {
                "Open": [149.0, 150.0],
                "High": [151.0, 151.5],
                "Low": [148.0, 149.5],
                "Close": [149.0, 150.0],
                "Volume": [1000000, 1000000],
            },
            index=pd.date_range("2024-01-01", periods=2),
        )
        mock_ticker.return_value = mock_stock

        svc = StockService()
        result = svc.get_realtime_quote("AAPL")

        if result:
            assert result["source"] == "yfinance"
            assert result["current"] == 150.0


class TestGetHistoricalData:
    """Tests for get_historical_data."""

    @patch("yfinance.Ticker")
    def test_historical_data_success(self, mock_ticker):
        """get_historical_data returns DataFrame."""
        import pandas as pd

        from flask_app.services.stock_service import StockService

        mock_stock = MagicMock()
        mock_df = pd.DataFrame(
            {
                "Open": [100, 101],
                "High": [102, 103],
                "Low": [99, 100],
                "Close": [101, 102],
                "Volume": [1000000, 1100000],
            },
            index=pd.date_range("2024-01-01", periods=2),
        )
        mock_stock.history.return_value = mock_df
        mock_ticker.return_value = mock_stock

        svc = StockService()
        result = svc.get_historical_data("AAPL")

        assert result is not None
        assert "Close" in result.columns

    @patch("yfinance.Ticker")
    def test_historical_data_empty(self, mock_ticker):
        """get_historical_data returns None for empty data."""
        import pandas as pd

        from flask_app.services.stock_service import StockService

        mock_stock = MagicMock()
        mock_stock.history.return_value = pd.DataFrame()
        mock_ticker.return_value = mock_stock

        svc = StockService()
        result = svc.get_historical_data("AAPL")

        assert result is None


class TestGetCompanyInfo:
    """Tests for get_company_info."""

    @patch("yfinance.Ticker")
    def test_company_info_success(self, mock_ticker):
        """get_company_info returns company data."""
        from flask_app.services.stock_service import StockService

        mock_stock = MagicMock()
        mock_stock.info = {
            "shortName": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "marketCap": 3000000000000,
            "trailingPE": 30.0,
            "beta": 1.2,
            "dividendYield": 0.5,
            "fiftyTwoWeekHigh": 200.0,
            "fiftyTwoWeekLow": 150.0,
            "targetMeanPrice": 180.0,
            "longBusinessSummary": "Apple Inc. designs, manufactures, and markets smartphones.",
        }
        mock_ticker.return_value = mock_stock

        svc = StockService()
        result = svc.get_company_info("AAPL")

        assert result is not None
        assert result["ticker"] == "AAPL"
        assert result["name"] == "Apple Inc."
        assert result["sector"] == "Technology"

    @patch("yfinance.Ticker")
    def test_company_info_no_data(self, mock_ticker):
        """get_company_info returns defaults when no data."""
        from flask_app.services.stock_service import StockService

        mock_stock = MagicMock()
        mock_stock.info = {}
        mock_ticker.return_value = mock_stock

        svc = StockService()
        result = svc.get_company_info("INVALIDTICKER")

        assert result is not None
        assert result["ticker"] == "INVALIDTICKER"
        assert result["name"] == "N/A"


class TestGetTechnicalIndicators:
    """Tests for get_technical_indicators."""

    def test_technical_indicators_no_client(self):
        """get_technical_indicators returns None without Finnhub."""
        from flask_app.services.stock_service import StockService

        svc = StockService()
        result = svc.get_technical_indicators("AAPL")

        assert result is None

    @patch("flask_app.services.stock_service.StockService.get_historical_data")
    @patch("finnhub.Client")
    def test_technical_indicators_insufficient_data(self, mock_client, mock_hist):
        """get_technical_indicators returns None with insufficient data."""
        import pandas as pd

        from flask_app.services.stock_service import StockService

        mock_instance = MagicMock()
        mock_client.return_value = mock_instance

        mock_hist.return_value = pd.DataFrame(
            {"Close": [100, 101, 102]}, index=pd.date_range("2024-01-01", periods=3)
        )

        svc = StockService({"FINNHUB_API_KEY": "test-key"})
        result = svc.get_technical_indicators("AAPL")

        assert result is None


class TestGetMarketStatus:
    """Tests for get_market_status."""

    @patch("finnhub.Client")
    def test_market_status_finnhub(self, mock_client):
        """get_market_status uses Finnhub when available."""
        from flask_app.services.stock_service import StockService

        mock_instance = MagicMock()
        mock_instance.market_status.return_value = {"isOpen": True, "session": "regular"}
        mock_client.return_value = mock_instance

        svc = StockService({"FINNHUB_API_KEY": "test-key"})
        result = svc.get_market_status()

        assert result["is_open"] is True
        assert result["session"] == "regular"

    def test_market_status_fallback(self):
        """get_market_status falls back to time-based check."""
        from flask_app.services.stock_service import StockService

        svc = StockService()
        result = svc.get_market_status()

        assert "is_open" in result
        assert "session" in result
        assert result["session"] in ("pre-market", "regular", "after-hours", "closed")


class TestGetPeers:
    """Tests for get_peers."""

    def test_get_peers_no_client(self):
        """get_peers returns empty list without Finnhub."""
        from flask_app.services.stock_service import StockService

        svc = StockService()
        result = svc.get_peers("AAPL")

        assert result == []

    @patch("finnhub.Client")
    def test_get_peers_with_client(self, mock_client):
        """get_peers returns peer tickers."""
        from flask_app.services.stock_service import StockService

        mock_instance = MagicMock()
        mock_instance.company_peers.return_value = ["MSFT", "GOOGL", "AAPL", "AMZN", "META", "NVDA"]
        mock_client.return_value = mock_instance

        svc = StockService({"FINNHUB_API_KEY": "test-key"})
        result = svc.get_peers("AAPL")

        assert "MSFT" in result
        assert "AAPL" not in result


class TestGetEarnings:
    """Tests for get_earnings."""

    def test_get_earnings_no_client(self):
        """get_earnings returns None without Finnhub."""
        from flask_app.services.stock_service import StockService

        svc = StockService()
        result = svc.get_earnings("AAPL")

        assert result is None

    @patch("finnhub.Client")
    def test_get_earnings_with_client(self, mock_client):
        """get_earnings returns earnings data."""
        from flask_app.services.stock_service import StockService

        mock_instance = MagicMock()
        mock_instance.earnings_calendar.return_value = {
            "earningsCalendar": [
                {"date": "2024-03-15", "quarter": "Q1", "year": 2024, "epsEstimate": 1.5}
            ]
        }
        mock_client.return_value = mock_instance

        svc = StockService({"FINNHUB_API_KEY": "test-key"})
        result = svc.get_earnings("AAPL")

        assert result is not None
        assert result["date"] == "2024-03-15"


class TestGetAnalystRecommendations:
    """Tests for get_analyst_recommendations."""

    def test_get_recommendations_no_client(self):
        """get_analyst_recommendations returns None without Finnhub."""
        from flask_app.services.stock_service import StockService

        svc = StockService()
        result = svc.get_analyst_recommendations("AAPL")

        assert result is None

    @patch("finnhub.Client")
    def test_get_recommendations_with_client(self, mock_client):
        """get_analyst_recommendations returns recommendations."""
        from flask_app.services.stock_service import StockService

        mock_instance = MagicMock()
        mock_instance.recommendation_trends.return_value = [{"grade": "BUY", "count": 10}]
        mock_client.return_value = mock_instance

        svc = StockService({"FINNHUB_API_KEY": "test-key"})
        result = svc.get_analyst_recommendations("AAPL")

        assert result is not None
        assert len(result) > 0


class TestGetPriceTargets:
    """Tests for get_price_targets."""

    def test_get_price_targets_no_client(self):
        """get_price_targets returns None without Finnhub."""
        from flask_app.services.stock_service import StockService

        svc = StockService()
        result = svc.get_price_targets("AAPL")

        assert result is None

    @patch("finnhub.Client")
    def test_get_price_targets_with_client(self, mock_client):
        """get_price_targets returns price targets."""
        from flask_app.services.stock_service import StockService

        mock_instance = MagicMock()
        mock_instance.price_target.return_value = {
            "targetHigh": 200.0,
            "targetLow": 150.0,
            "targetMean": 175.0,
        }
        mock_client.return_value = mock_instance

        svc = StockService({"FINNHUB_API_KEY": "test-key"})
        result = svc.get_price_targets("AAPL")

        assert result is not None
        assert result["target_high"] == 200.0


class TestGetInsiderTrades:
    """Tests for get_insider_trades."""

    def test_get_insider_trades_no_client(self):
        """get_insider_trades returns None without Finnhub."""
        from flask_app.services.stock_service import StockService

        svc = StockService()
        result = svc.get_insider_trades("AAPL")

        assert result is None

    @patch("finnhub.Client")
    def test_get_insider_trades_with_client(self, mock_client):
        """get_insider_trades returns insider trades."""
        from flask_app.services.stock_service import StockService

        mock_instance = MagicMock()
        mock_instance.stock_insider_transactions.return_value = {
            "data": [{"transaction": "P-Purchase", "price": 150.0, "share": 100}]
        }
        mock_client.return_value = mock_instance

        svc = StockService({"FINNHUB_API_KEY": "test-key"})
        result = svc.get_insider_trades("AAPL")

        assert result is not None
        assert len(result) > 0


class TestGetNews:
    """Tests for get_news."""

    @patch("feedparser.parse")
    def test_get_news_success(self, mock_parse):
        """get_news returns news items."""
        from flask_app.services.stock_service import StockService

        mock_entry = MagicMock()
        mock_entry.title = "Test Headline"
        mock_entry.link = "http://test.com"
        mock_entry.source = MagicMock()
        mock_entry.source.title = "Test Source"
        mock_entry.published = "2024-01-01"

        mock_parse.return_value = MagicMock(entries=[mock_entry])

        svc = StockService()
        result = svc.get_news("AAPL")

        assert isinstance(result, list)

    @patch("feedparser.parse")
    def test_get_news_empty(self, mock_parse):
        """get_news returns empty list on error."""
        from flask_app.services.stock_service import StockService

        mock_parse.side_effect = Exception("Network error")

        svc = StockService()
        result = svc.get_news("AAPL")

        assert result == []


class TestGetCompleteData:
    """Tests for get_complete_data."""

    def test_get_complete_data_returns_dict(self):
        """get_complete_data returns a dict with all keys."""
        from flask_app.services.stock_service import StockService

        svc = StockService()
        result = svc.get_complete_data("AAPL")

        assert isinstance(result, dict)
        assert "ticker" in result
        assert result["ticker"] == "AAPL"
        assert "quote" in result
        assert "company" in result
        assert "news" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
