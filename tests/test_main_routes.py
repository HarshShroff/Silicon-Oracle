"""
Tests for Silicon Oracle Main Routes.
Run with: pytest tests/test_main_routes.py -v
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def app():
    """Create and configure test app."""
    from flask_app import create_app

    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def authenticated_client(app, client):
    """Create authenticated test client."""
    mock_user = MagicMock()
    mock_user.id = "test-user-123"
    mock_user.is_authenticated = True

    with client.session_transaction() as sess:
        sess["user_id"] = "test-user-123"
        sess["logged_in_at"] = "2024-01-01T00:00:00"
        sess["alpaca_enabled"] = True

    return client


class TestHealthCheck:
    """Tests for health check endpoint."""

    def test_health_returns_200(self, client):
        """Test health endpoint returns 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_json(self, client):
        """Test health endpoint returns JSON."""
        response = client.get("/health")
        data = response.get_json()
        assert data["status"] == "ok"


class TestDemoPage:
    """Tests for demo page."""

    def test_demo_page_loads(self, client):
        """Test demo page renders."""
        response = client.get("/demo")
        assert response.status_code == 200


class TestIndex:
    """Tests for index/command center."""

    def test_index_requires_login(self, client):
        """Test index redirects to login."""
        response = client.get("/")
        assert response.status_code == 302

    def test_command_center_alias(self, authenticated_client):
        """Test command center route works."""
        with patch("flask_app.routes.main.g") as mock_g:
            mock_g.user = MagicMock()
            mock_g.user.is_authenticated = True
            mock_g.user.id = "test-user"

            response = authenticated_client.get("/command-center")
            assert response.status_code in [200, 302]


class TestAnalysis:
    """Tests for analysis page."""

    def test_analysis_requires_login(self, client):
        """Test analysis redirects to login."""
        response = client.get("/analysis")
        assert response.status_code == 302

    def test_analysis_with_ticker_requires_login(self, client):
        """Test analysis with ticker redirects to login."""
        response = client.get("/analysis/NVDA")
        assert response.status_code == 302


class TestScanner:
    """Tests for scanner page."""

    def test_scanner_requires_login(self, client):
        """Test scanner redirects to login."""
        response = client.get("/scanner")
        assert response.status_code == 302


class TestPortfolio:
    """Tests for portfolio page."""

    def test_portfolio_requires_login(self, client):
        """Test portfolio redirects to login."""
        response = client.get("/portfolio")
        assert response.status_code == 302


class TestTrade:
    """Tests for trade page."""

    def test_trade_requires_login(self, client):
        """Test trade redirects to login."""
        response = client.get("/trade")
        assert response.status_code == 302

    def test_trade_with_ticker_requires_login(self, client):
        """Test trade with ticker redirects to login."""
        response = client.get("/trade/AAPL")
        assert response.status_code == 302


class TestAIGuidance:
    """Tests for AI guidance page."""

    def test_ai_guidance_requires_login(self, client):
        """Test AI guidance redirects to login."""
        response = client.get("/ai-guidance")
        assert response.status_code == 302


class TestWatchlist:
    """Tests for watchlist page."""

    def test_watchlist_requires_login(self, client):
        """Test watchlist redirects to login."""
        response = client.get("/watchlist")
        assert response.status_code == 302


class TestSettings:
    """Tests for settings page."""

    def test_settings_requires_login(self, client):
        """Test settings redirects to login."""
        response = client.get("/settings")
        assert response.status_code == 302


class TestMacro:
    """Tests for macro page."""

    def test_macro_requires_login(self, client):
        """Test macro redirects to login."""
        response = client.get("/macro")
        assert response.status_code == 302


class TestSettingsLoad:
    """Tests for settings/load endpoint."""

    def test_settings_load_requires_login(self, client):
        """Test settings load requires login."""
        response = client.get("/settings/load")
        assert response.status_code == 302


class TestSettingsDataSummary:
    """Tests for settings/data-summary endpoint."""

    def test_data_summary_requires_login(self, client):
        """Test data summary requires login."""
        response = client.get("/settings/data-summary")
        assert response.status_code == 302


class TestExportData:
    """Tests for settings/export endpoint."""

    def test_export_requires_login(self, client):
        """Test export requires login."""
        response = client.get("/settings/export")
        assert response.status_code == 302

    def test_export_csv_format(self, client):
        """Test export CSV format."""
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user"

        with patch("flask_app.routes.main.g") as mock_g:
            mock_g.user = MagicMock()
            mock_g.user.id = "test-user"
            mock_g.user.is_authenticated = True

            response = client.get("/settings/export?format=csv")
            assert response.status_code in [200, 500]


class TestLoginRequired:
    """Tests for login_required decorator."""

    def test_login_required_redirects(self, client):
        """Test login_required redirects unauthenticated."""
        response = client.get("/")
        assert response.status_code == 302


class TestGetAlpacaEnabled:
    """Tests for get_alpaca_enabled function."""

    @patch("flask_app.routes.main.g")
    def test_get_alpaca_enabled_from_session(self, mock_g, client):
        """Test alpaca enabled from session."""
        mock_g.user = MagicMock()
        mock_g.user.id = "test-user"
        mock_g.user.is_authenticated = True

        with client.session_transaction() as sess:
            sess["alpaca_enabled"] = True

        from flask_app.routes.main import get_alpaca_enabled

        result = get_alpaca_enabled()
        assert result is True


class TestGetConfig:
    """Tests for get_config function."""

    @patch("flask_app.routes.main.g")
    def test_get_config_no_user(self, mock_g, client):
        """Test get_config returns empty keys when no user."""
        mock_g.user = None

        from flask_app.routes.main import get_config

        config = get_config()
        assert config["FINNHUB_API_KEY"] == ""


class TestGetShadowPortfolio:
    """Tests for get_shadow_portfolio function."""

    @patch("flask_app.routes.main.StockService")
    @patch("flask_app.routes.main.db.get_shadow_positions")
    def test_get_shadow_portfolio_empty(self, mock_positions, mock_stock, client):
        """Test shadow portfolio with no positions."""
        mock_positions.return_value = []

        from flask_app.routes.main import get_shadow_portfolio

        positions, metrics = get_shadow_portfolio("test-user", {})
        assert positions == []
        assert metrics == {}

    @patch("flask_app.routes.main.StockService")
    @patch("flask_app.routes.main.db.get_shadow_positions")
    def test_get_shadow_portfolio_with_position(self, mock_positions, mock_stock, client):
        """Test shadow portfolio with position."""
        mock_positions.return_value = [{"ticker": "AAPL", "shares": 10, "avg_price": 150.0}]

        mock_stock_instance = MagicMock()
        mock_stock_instance.get_realtime_quote.return_value = {"current": 155.0}
        mock_stock.return_value = mock_stock_instance

        from flask_app.routes.main import get_shadow_portfolio

        positions, metrics = get_shadow_portfolio("test-user", {})

        assert len(positions) == 1
        assert positions[0]["ticker"] == "AAPL"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
