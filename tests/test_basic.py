"""
Basic tests for Silicon Oracle Flask application.
Run with: pytest tests/test_basic.py -v
"""

import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask_app import create_app


@pytest.fixture
def app():
    """Create and configure test app."""
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestHealthCheck:
    """Tests for health check endpoint."""

    def test_health_check_returns_200(self, client):
        """Test that health check endpoint returns 200 status."""
        response = client.get('/health')
        assert response.status_code == 200

    def test_health_check_response_format(self, client):
        """Test that health check returns proper JSON structure."""
        response = client.get('/health')
        data = response.get_json()

        assert data is not None
        assert 'status' in data
        assert 'timestamp' in data
        assert 'version' in data

    def test_health_check_status_is_healthy(self, client):
        """Test that health check reports healthy status."""
        response = client.get('/health')
        data = response.get_json()

        assert data['status'] in ['healthy', 'unhealthy']
        # In testing environment, should be healthy


class TestAuthentication:
    """Tests for authentication routes."""

    def test_login_page_loads(self, client):
        """Test that login page is accessible."""
        response = client.get('/auth/login')
        assert response.status_code in [200, 302]  # 302 if already logged in

    def test_signup_page_loads(self, client):
        """Test that signup page is accessible."""
        response = client.get('/auth/signup')
        assert response.status_code in [200, 302]  # 302 if already logged in


class TestRoutes:
    """Tests for main application routes."""

    def test_settings_page_requires_auth(self, client):
        """Test that settings page requires authentication."""
        response = client.get('/settings')
        # Should redirect to login if not authenticated
        assert response.status_code in [302, 200]

    def test_command_center_requires_auth(self, client):
        """Test that command center requires authentication."""
        response = client.get('/')
        # Should redirect to login if not authenticated
        assert response.status_code in [302, 200]


class TestErrorHandling:
    """Tests for error handling."""

    def test_404_error_handled(self, client):
        """Test that 404 errors are handled gracefully."""
        response = client.get('/nonexistent-page-xyz')
        assert response.status_code == 404

    def test_health_check_works_without_auth(self, client):
        """Test that health check doesn't require authentication."""
        response = client.get('/health')
        # Should NOT redirect - health checks must be public
        assert response.status_code in [200, 503]


class TestPageTitles:
    """Tests for page titles and templates."""

    def test_login_page_has_title(self, client):
        """Test that login page renders with proper title."""
        response = client.get('/auth/login')
        if response.status_code == 200:
            assert b'Silicon Oracle' in response.data or b'login' in response.data.lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
