"""
Tests for flask_app/services/portfolio_service.py — performance metrics and trade logic.
"""

from unittest.mock import MagicMock, patch

import pytest

from flask_app.services.portfolio_service import PortfolioService


@pytest.fixture
def svc():
    return PortfolioService(user_id="test-user-123")


@pytest.fixture
def svc_no_user():
    return PortfolioService(user_id="")


class TestInit:
    def test_stores_user_id(self, svc):
        assert svc.user_id == "test-user-123"


class TestGetPositions:
    def test_returns_empty_without_user(self, svc_no_user):
        assert svc_no_user.get_positions() == []

    def test_calls_db_with_user_id(self, svc):
        with patch("flask_app.services.portfolio_service.db") as mock_db:
            mock_db.get_user_positions.return_value = [{"ticker": "AAPL"}]
            result = svc.get_positions()
        assert result == [{"ticker": "AAPL"}]


class TestGetTradeHistory:
    def test_returns_empty_without_user(self, svc_no_user):
        assert svc_no_user.get_trade_history() == []

    def test_normalizes_trade_fields(self, svc):
        raw = [
            {
                "ticker": "AAPL",
                "action": "BUY",
                "shares": 10,
                "price": 150.0,
                "total_value": None,  # missing
                "reason": "test",
                "timestamp": "2025-01-01",
                "source": None,
            }
        ]
        with patch("flask_app.services.portfolio_service.db") as mock_db:
            mock_db.get_user_trades.return_value = raw
            result = svc.get_trade_history()

        assert len(result) == 1
        trade = result[0]
        # total_value should be computed as shares * price
        assert trade["total_value"] == 1500.0
        # source is None in raw data — .get("source", "manual") returns None when key exists

    def test_uses_existing_total_value(self, svc):
        raw = [
            {
                "ticker": "MSFT",
                "action": "SELL",
                "shares": 5,
                "price": 300.0,
                "total_value": 1500.0,
                "reason": None,
                "timestamp": "2025-02-01",
                "source": "alpaca",
            }
        ]
        with patch("flask_app.services.portfolio_service.db") as mock_db:
            mock_db.get_user_trades.return_value = raw
            result = svc.get_trade_history()
        assert result[0]["total_value"] == 1500.0
        assert result[0]["source"] == "alpaca"


class TestPerformanceMetrics:
    def test_empty_trades_returns_zeros(self, svc):
        with patch.object(svc, "get_trade_history", return_value=[]):
            result = svc.get_performance_metrics()
        assert result["total_trades"] == 0
        assert result["wins"] == 0
        assert result["losses"] == 0
        assert result["win_rate"] == 0
        assert result["total_realized_pnl"] == 0

    def test_profitable_trade(self, svc):
        trades = [
            {"ticker": "AAPL", "action": "BUY", "shares": 10, "price": 100.0},
            {"ticker": "AAPL", "action": "SELL", "shares": 10, "price": 150.0},
        ]
        with patch.object(svc, "get_trade_history", return_value=trades):
            result = svc.get_performance_metrics()
        assert result["wins"] == 1
        assert result["losses"] == 0
        assert result["total_realized_pnl"] == pytest.approx(500.0)
        assert result["win_rate"] == 100.0

    def test_losing_trade(self, svc):
        trades = [
            {"ticker": "TSLA", "action": "BUY", "shares": 5, "price": 200.0},
            {"ticker": "TSLA", "action": "SELL", "shares": 5, "price": 150.0},
        ]
        with patch.object(svc, "get_trade_history", return_value=trades):
            result = svc.get_performance_metrics()
        assert result["losses"] == 1
        assert result["wins"] == 0
        assert result["total_realized_pnl"] == pytest.approx(-250.0)
        assert result["win_rate"] == 0.0

    def test_mixed_win_loss(self, svc):
        trades = [
            # AAPL: win
            {"ticker": "AAPL", "action": "BUY", "shares": 10, "price": 100.0},
            {"ticker": "AAPL", "action": "SELL", "shares": 10, "price": 120.0},
            # TSLA: loss
            {"ticker": "TSLA", "action": "BUY", "shares": 5, "price": 300.0},
            {"ticker": "TSLA", "action": "SELL", "shares": 5, "price": 250.0},
        ]
        with patch.object(svc, "get_trade_history", return_value=trades):
            result = svc.get_performance_metrics()
        assert result["wins"] == 1
        assert result["losses"] == 1
        assert result["win_rate"] == 50.0

    def test_only_buys_no_sells(self, svc):
        """Positions not yet sold — no PnL calculated."""
        trades = [
            {"ticker": "AAPL", "action": "BUY", "shares": 10, "price": 100.0},
        ]
        with patch.object(svc, "get_trade_history", return_value=trades):
            result = svc.get_performance_metrics()
        assert result["wins"] == 0
        assert result["losses"] == 0
        assert result["total_realized_pnl"] == 0

    def test_only_sells_no_buys(self, svc):
        """Sells without buys — no PnL calculated."""
        trades = [
            {"ticker": "AAPL", "action": "SELL", "shares": 10, "price": 150.0},
        ]
        with patch.object(svc, "get_trade_history", return_value=trades):
            result = svc.get_performance_metrics()
        assert result["wins"] == 0
        assert result["losses"] == 0

    def test_weighted_average_price(self, svc):
        """Multiple buys at different prices → correct weighted avg."""
        trades = [
            {"ticker": "AAPL", "action": "BUY", "shares": 10, "price": 100.0},
            {"ticker": "AAPL", "action": "BUY", "shares": 10, "price": 120.0},
            # avg_buy = (10*100 + 10*120) / 20 = 110
            {"ticker": "AAPL", "action": "SELL", "shares": 20, "price": 130.0},
            # pnl = (130 - 110) * 20 = 400
        ]
        with patch.object(svc, "get_trade_history", return_value=trades):
            result = svc.get_performance_metrics()
        assert result["total_realized_pnl"] == pytest.approx(400.0)

    def test_total_trades_count(self, svc):
        trades = [
            {"ticker": "AAPL", "action": "BUY", "shares": 10, "price": 100.0},
            {"ticker": "MSFT", "action": "BUY", "shares": 5, "price": 200.0},
            {"ticker": "AAPL", "action": "SELL", "shares": 10, "price": 110.0},
        ]
        with patch.object(svc, "get_trade_history", return_value=trades):
            result = svc.get_performance_metrics()
        assert result["total_trades"] == 3


class TestAddTrade:
    def test_returns_false_without_user(self, svc_no_user):
        assert svc_no_user.add_trade("AAPL", "BUY", 10, 150.0) is False

    def test_returns_false_without_db(self, svc):
        with patch("flask_app.services.portfolio_service.db") as mock_db:
            mock_db.get_supabase_client.return_value = None
            result = svc.add_trade("AAPL", "BUY", 10, 150.0)
        assert result is False

    def test_returns_true_on_success(self, svc):
        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock()
        with patch("flask_app.services.portfolio_service.db") as mock_db:
            mock_db.get_supabase_client.return_value = mock_client
            mock_db.upsert_position.return_value = True
            result = svc.add_trade("AAPL", "BUY", 10, 150.0)
        assert result is True

    def test_upsert_called_on_buy(self, svc):
        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock()
        with patch("flask_app.services.portfolio_service.db") as mock_db:
            mock_db.get_supabase_client.return_value = mock_client
            svc.add_trade("AAPL", "BUY", 10, 150.0)
            mock_db.upsert_position.assert_called_once()

    def test_upsert_not_called_on_sell(self, svc):
        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock()
        with patch("flask_app.services.portfolio_service.db") as mock_db:
            mock_db.get_supabase_client.return_value = mock_client
            svc.add_trade("AAPL", "SELL", 5, 180.0)
            mock_db.upsert_position.assert_not_called()
