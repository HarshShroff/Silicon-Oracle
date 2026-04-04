"""
Tests for Silicon Oracle Trading Service.
Run with: pytest tests/test_trading_service.py -v
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestTradingServiceInit:
    """Tests for TradingService initialization."""

    def test_init_without_config(self):
        """TradingService initializes without config."""
        from flask_app.services.trading_service import TradingService

        svc = TradingService()
        assert svc is not None
        assert svc.config == {}

    def test_init_with_config(self):
        """TradingService stores provided config."""
        from flask_app.services.trading_service import TradingService

        svc = TradingService({"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"})
        assert svc.config.get("ALPACA_API_KEY") == "test"

    def test_init_no_alpaca_keys(self):
        """TradingService initializes with empty config."""
        from flask_app.services.trading_service import TradingService

        svc = TradingService({})
        assert svc.trading_client is None


class TestIsConnected:
    """Tests for is_connected."""

    def test_not_connected_without_client(self):
        """is_connected returns False without client."""
        from flask_app.services.trading_service import TradingService

        svc = TradingService()
        assert svc.is_connected() is False

    @patch("alpaca.trading.client.TradingClient")
    def test_connected_with_client(self, mock_client):
        """is_connected returns True with client."""
        from flask_app.services.trading_service import TradingService

        mock_client.return_value = MagicMock()
        svc = TradingService({"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"})
        assert svc.is_connected() is True


class TestGetAccount:
    """Tests for get_account."""

    def test_get_account_no_client(self):
        """get_account returns None without client."""
        from flask_app.services.trading_service import TradingService

        svc = TradingService()
        result = svc.get_account()
        assert result is None

    @patch("alpaca.trading.client.TradingClient")
    def test_get_account_success(self, mock_client):
        """get_account returns account data."""
        from flask_app.services.trading_service import TradingService

        mock_instance = MagicMock()
        mock_instance.get_account.return_value = MagicMock(
            buying_power=10000.0,
            portfolio_value=50000.0,
            cash=10000.0,
            equity=50000.0,
            currency="USD",
            status="ACTIVE",
        )
        mock_client.return_value = mock_instance

        svc = TradingService({"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"})
        result = svc.get_account()

        assert result is not None
        assert result["buying_power"] == 10000.0

    @patch("alpaca.trading.client.TradingClient")
    def test_get_account_error(self, mock_client):
        """get_account returns None on error."""
        from flask_app.services.trading_service import TradingService

        mock_instance = MagicMock()
        mock_instance.get_account.side_effect = Exception("API Error")
        mock_client.return_value = mock_instance

        svc = TradingService({"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"})
        result = svc.get_account()

        assert result is None


class TestGetPositions:
    """Tests for get_positions."""

    def test_get_positions_no_client(self):
        """get_positions returns empty list without client."""
        from flask_app.services.trading_service import TradingService

        svc = TradingService()
        result = svc.get_positions()
        assert result == []

    @patch("alpaca.trading.client.TradingClient")
    def test_get_positions_success(self, mock_client):
        """get_positions returns position list."""
        from flask_app.services.trading_service import TradingService

        mock_pos = MagicMock()
        mock_pos.symbol = "AAPL"
        mock_pos.qty = 10.0
        mock_pos.avg_entry_price = 150.0
        mock_pos.current_price = 155.0
        mock_pos.market_value = 1550.0
        mock_pos.unrealized_pl = 50.0
        mock_pos.unrealized_plpc = 0.05
        mock_pos.side = "long"

        mock_instance = MagicMock()
        mock_instance.get_all_positions.return_value = [mock_pos]
        mock_client.return_value = mock_instance

        svc = TradingService({"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"})
        result = svc.get_positions()

        assert len(result) == 1
        assert result[0]["ticker"] == "AAPL"

    @patch("alpaca.trading.client.TradingClient")
    def test_get_positions_error(self, mock_client):
        """get_positions returns empty list on error."""
        from flask_app.services.trading_service import TradingService

        mock_instance = MagicMock()
        mock_instance.get_all_positions.side_effect = Exception("API Error")
        mock_client.return_value = mock_instance

        svc = TradingService({"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"})
        result = svc.get_positions()

        assert result == []


class TestGetPosition:
    """Tests for get_position."""

    def test_get_position_no_client(self):
        """get_position returns None without client."""
        from flask_app.services.trading_service import TradingService

        svc = TradingService()
        result = svc.get_position("AAPL")
        assert result is None

    @patch("alpaca.trading.client.TradingClient")
    def test_get_position_success(self, mock_client):
        """get_position returns position data."""
        from flask_app.services.trading_service import TradingService

        mock_pos = MagicMock()
        mock_pos.symbol = "AAPL"
        mock_pos.qty = 10.0
        mock_pos.avg_entry_price = 150.0
        mock_pos.current_price = 155.0
        mock_pos.unrealized_pl = 50.0
        mock_pos.unrealized_plpc = 0.05

        mock_instance = MagicMock()
        mock_instance.get_open_position.return_value = mock_pos
        mock_client.return_value = mock_instance

        svc = TradingService({"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"})
        result = svc.get_position("AAPL")

        assert result is not None
        assert result["ticker"] == "AAPL"

    @patch("alpaca.trading.client.TradingClient")
    def test_get_position_not_found(self, mock_client):
        """get_position returns None when position not found."""
        from flask_app.services.trading_service import TradingService

        mock_instance = MagicMock()
        mock_instance.get_open_position.side_effect = Exception("Not found")
        mock_client.return_value = mock_instance

        svc = TradingService({"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"})
        result = svc.get_position("INVALID")

        assert result is None


class TestSubmitOrder:
    """Tests for submit_order."""

    def test_submit_order_no_client(self):
        """submit_order returns error without client."""
        from flask_app.services.trading_service import TradingService

        svc = TradingService()
        result = svc.submit_order("AAPL", 10, "buy")
        assert result["success"] is False

    @patch("alpaca.trading.client.TradingClient")
    def test_submit_order_market_success(self, mock_client):
        """submit_order returns success for market order."""
        from flask_app.services.trading_service import TradingService

        mock_order = MagicMock()
        mock_order.id = "order-123"
        mock_order.status = "accepted"
        mock_order.symbol = "AAPL"
        mock_order.qty = 10.0
        mock_order.side = "buy"

        mock_instance = MagicMock()
        mock_instance.submit_order.return_value = mock_order
        mock_client.return_value = mock_instance

        svc = TradingService({"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"})
        result = svc.submit_order("AAPL", 10, "buy")

        assert result["success"] is True

    @patch("alpaca.trading.client.TradingClient")
    def test_submit_order_limit(self, mock_client):
        """submit_order handles limit orders."""
        from flask_app.services.trading_service import TradingService

        mock_order = MagicMock()
        mock_order.id = "order-123"
        mock_order.status = "accepted"
        mock_order.symbol = "AAPL"
        mock_order.qty = 10.0
        mock_order.side = "buy"

        mock_instance = MagicMock()
        mock_instance.submit_order.return_value = mock_order
        mock_client.return_value = mock_instance

        svc = TradingService({"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"})
        result = svc.submit_order("AAPL", 10, "buy", "limit", 155.0)

        assert result["success"] is True

    @patch("alpaca.trading.client.TradingClient")
    def test_submit_order_error(self, mock_client):
        """submit_order returns error on failure."""
        from flask_app.services.trading_service import TradingService

        mock_instance = MagicMock()
        mock_instance.submit_order.side_effect = Exception("Insufficient funds")
        mock_client.return_value = mock_instance

        svc = TradingService({"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"})
        result = svc.submit_order("AAPL", 10000, "buy")

        assert result["success"] is False


class TestBuyAndSell:
    """Tests for buy and sell methods."""

    @patch("flask_app.services.trading_service.TradingService.submit_order")
    def test_buy_calls_submit_order(self, mock_submit):
        """buy calls submit_order with correct side."""
        from flask_app.services.trading_service import TradingService

        mock_submit.return_value = {"success": True}
        svc = TradingService()
        result = svc.buy("AAPL", 10)

        mock_submit.assert_called_once_with("AAPL", 10, "buy", "market", None)
        assert result["success"] is True

    @patch("flask_app.services.trading_service.TradingService.submit_order")
    def test_sell_calls_submit_order(self, mock_submit):
        """sell calls submit_order with correct side."""
        from flask_app.services.trading_service import TradingService

        mock_submit.return_value = {"success": True}
        svc = TradingService()
        result = svc.sell("AAPL", 10)

        mock_submit.assert_called_once_with("AAPL", 10, "sell", "market", None)
        assert result["success"] is True


class TestClosePosition:
    """Tests for close_position."""

    def test_close_position_no_client(self):
        """close_position returns error without client."""
        from flask_app.services.trading_service import TradingService

        svc = TradingService()
        result = svc.close_position("AAPL")
        assert result["success"] is False

    @patch("alpaca.trading.client.TradingClient")
    def test_close_position_success(self, mock_client):
        """close_position returns success."""
        from flask_app.services.trading_service import TradingService

        mock_instance = MagicMock()
        mock_client.return_value = mock_instance

        svc = TradingService({"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"})
        result = svc.close_position("AAPL")

        assert result["success"] is True

    @patch("alpaca.trading.client.TradingClient")
    def test_close_position_error(self, mock_client):
        """close_position returns error on failure."""
        from flask_app.services.trading_service import TradingService

        mock_instance = MagicMock()
        mock_instance.close_position.side_effect = Exception("Not found")
        mock_client.return_value = mock_instance

        svc = TradingService({"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"})
        result = svc.close_position("INVALID")

        assert result["success"] is False


class TestCancelOrder:
    """Tests for cancel_order."""

    def test_cancel_order_no_client(self):
        """cancel_order returns error without client."""
        from flask_app.services.trading_service import TradingService

        svc = TradingService()
        result = svc.cancel_order("order-123")
        assert result["success"] is False

    @patch("alpaca.trading.client.TradingClient")
    def test_cancel_order_success(self, mock_client):
        """cancel_order returns success."""
        from flask_app.services.trading_service import TradingService

        mock_instance = MagicMock()
        mock_client.return_value = mock_instance

        svc = TradingService({"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"})
        result = svc.cancel_order("order-123")

        assert result["success"] is True

    @patch("alpaca.trading.client.TradingClient")
    def test_cancel_order_error(self, mock_client):
        """cancel_order returns error on failure."""
        from flask_app.services.trading_service import TradingService

        mock_instance = MagicMock()
        mock_instance.cancel_order_by_id.side_effect = Exception("Already filled")
        mock_client.return_value = mock_instance

        svc = TradingService({"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"})
        result = svc.cancel_order("order-123")

        assert result["success"] is False


class TestGetOrders:
    """Tests for get_orders."""

    def test_get_orders_no_client(self):
        """get_orders returns empty list without client."""
        from flask_app.services.trading_service import TradingService

        svc = TradingService()
        result = svc.get_orders()
        assert result == []

    @patch("alpaca.trading.client.TradingClient")
    def test_get_orders_success(self, mock_client):
        """get_orders returns order list."""
        from flask_app.services.trading_service import TradingService

        mock_order = MagicMock()
        mock_order.id = "order-123"
        mock_order.symbol = "AAPL"
        mock_order.side = "buy"
        mock_order.qty = 10.0
        mock_order.filled_qty = 0.0
        mock_order.status = "new"
        mock_order.type = "market"
        mock_order.submitted_at = None
        mock_order.filled_at = None
        mock_order.filled_avg_price = 0.0

        mock_instance = MagicMock()
        mock_instance.get_orders.return_value = [mock_order]
        mock_client.return_value = mock_instance

        svc = TradingService({"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"})
        result = svc.get_orders()

        assert len(result) == 1

    @patch("alpaca.trading.client.TradingClient")
    def test_get_orders_error(self, mock_client):
        """get_orders returns empty list on error."""
        from flask_app.services.trading_service import TradingService

        mock_instance = MagicMock()
        mock_instance.get_orders.side_effect = Exception("API Error")
        mock_client.return_value = mock_instance

        svc = TradingService({"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"})
        result = svc.get_orders()

        assert result == []


class TestIsMarketOpen:
    """Tests for is_market_open."""

    def test_is_market_open_no_client(self):
        """is_market_open returns False without client."""
        from flask_app.services.trading_service import TradingService

        svc = TradingService()
        result = svc.is_market_open()
        assert result is False

    @patch("alpaca.trading.client.TradingClient")
    def test_is_market_open_true(self, mock_client):
        """is_market_open returns True when market is open."""
        from flask_app.services.trading_service import TradingService

        mock_clock = MagicMock()
        mock_clock.is_open = True

        mock_instance = MagicMock()
        mock_instance.get_clock.return_value = mock_clock
        mock_client.return_value = mock_instance

        svc = TradingService({"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"})
        result = svc.is_market_open()

        assert result is True

    @patch("alpaca.trading.client.TradingClient")
    def test_is_market_open_false(self, mock_client):
        """is_market_open returns False when market is closed."""
        from flask_app.services.trading_service import TradingService

        mock_clock = MagicMock()
        mock_clock.is_open = False

        mock_instance = MagicMock()
        mock_instance.get_clock.return_value = mock_clock
        mock_client.return_value = mock_instance

        svc = TradingService({"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"})
        result = svc.is_market_open()

        assert result is False


class TestGetPortfolioHistory:
    """Tests for get_portfolio_history."""

    def test_get_portfolio_history_no_client(self):
        """get_portfolio_history returns None without client."""
        from flask_app.services.trading_service import TradingService

        svc = TradingService()
        result = svc.get_portfolio_history()
        assert result is None

    @patch("alpaca.trading.client.TradingClient")
    def test_get_portfolio_history_success(self, mock_client):
        """get_portfolio_history returns DataFrame."""

        from flask_app.services.trading_service import TradingService

        mock_history = MagicMock()
        mock_history.timestamp = [1704067200, 1704153600]
        mock_history.equity = [10000.0, 10100.0]
        mock_history.profit_loss = [0.0, 100.0]
        mock_history.profit_loss_pct = [0.0, 1.0]

        mock_instance = MagicMock()
        mock_instance.get_portfolio_history.return_value = mock_history
        mock_client.return_value = mock_instance

        svc = TradingService({"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"})
        result = svc.get_portfolio_history()

        assert result is not None

    @patch("alpaca.trading.client.TradingClient")
    def test_get_portfolio_history_error(self, mock_client):
        """get_portfolio_history returns None on error."""
        from flask_app.services.trading_service import TradingService

        mock_instance = MagicMock()
        mock_instance.get_portfolio_history.side_effect = Exception("API Error")
        mock_client.return_value = mock_instance

        svc = TradingService({"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"})
        result = svc.get_portfolio_history()

        assert result is None


class TestGetWatchlists:
    """Tests for get_watchlists."""

    def test_get_watchlists_no_client(self):
        """get_watchlists returns empty list without client."""
        from flask_app.services.trading_service import TradingService

        svc = TradingService()
        result = svc.get_watchlists()
        assert result == []

    @patch("alpaca.trading.client.TradingClient")
    def test_get_watchlists_success(self, mock_client):
        """get_watchlists returns watchlist data."""
        from flask_app.services.trading_service import TradingService

        mock_wl = MagicMock()
        mock_wl.id = "wl-123"
        mock_wl.name = "Tech"
        mock_wl.assets = []

        mock_instance = MagicMock()
        mock_instance.get_watchlists.return_value = [mock_wl]
        mock_client.return_value = mock_instance

        svc = TradingService({"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"})
        result = svc.get_watchlists()

        assert len(result) == 1

    @patch("alpaca.trading.client.TradingClient")
    def test_get_watchlists_error(self, mock_client):
        """get_watchlists returns empty list on error."""
        from flask_app.services.trading_service import TradingService

        mock_instance = MagicMock()
        mock_instance.get_watchlists.side_effect = Exception("API Error")
        mock_client.return_value = mock_instance

        svc = TradingService({"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"})
        result = svc.get_watchlists()

        assert result == []


class TestCreateWatchlist:
    """Tests for create_watchlist."""

    def test_create_watchlist_no_client(self):
        """create_watchlist returns None without client."""
        from flask_app.services.trading_service import TradingService

        svc = TradingService()
        result = svc.create_watchlist("Tech")
        assert result is None

    @patch("alpaca.trading.client.TradingClient")
    def test_create_watchlist_success(self, mock_client):
        """create_watchlist returns watchlist data."""
        from flask_app.services.trading_service import TradingService

        mock_wl = MagicMock()
        mock_wl.id = "wl-123"
        mock_wl.name = "Tech"
        mock_wl.assets = []

        mock_instance = MagicMock()
        mock_instance.create_watchlist.return_value = mock_wl
        mock_client.return_value = mock_instance

        svc = TradingService({"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"})
        result = svc.create_watchlist("Tech", ["AAPL", "NVDA"])

        assert result is not None

    @patch("alpaca.trading.client.TradingClient")
    def test_create_watchlist_error(self, mock_client):
        """create_watchlist returns None on error."""
        from flask_app.services.trading_service import TradingService

        mock_instance = MagicMock()
        mock_instance.create_watchlist.side_effect = Exception("API Error")
        mock_client.return_value = mock_instance

        svc = TradingService({"ALPACA_API_KEY": "test", "ALPACA_SECRET_KEY": "test"})
        result = svc.create_watchlist("Tech")

        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
