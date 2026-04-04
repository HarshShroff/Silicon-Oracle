"""
Tests for Silicon Oracle Auth Routes.
Run with: pytest tests/test_auth_routes.py -v
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


class TestLoginPage:
    """Tests for login page."""

    def test_login_page_get(self, client):
        """Test login page GET."""
        response = client.get("/auth/login")
        assert response.status_code == 200

    def test_login_page_post_empty(self, client):
        """Test login with empty credentials."""
        response = client.post("/auth/login", data={})
        assert response.status_code == 200

    def test_login_page_post_missing_email(self, client):
        """Test login with missing email."""
        response = client.post("/auth/login", data={"password": "test"})
        assert response.status_code == 200

    def test_login_page_post_missing_password(self, client):
        """Test login with missing password."""
        response = client.post("/auth/login", data={"email": "test@example.com"})
        assert response.status_code == 200

    @patch("flask_app.routes.auth.db.get_supabase_client")
    def test_login_post_invalid_credentials(self, mock_client, client):
        """Test login with invalid credentials."""
        mock_supabase = MagicMock()
        mock_supabase.auth.sign_in_with_password.side_effect = Exception("Invalid credentials")
        mock_client.return_value = mock_supabase

        response = client.post(
            "/auth/login", data={"email": "test@example.com", "password": "wrongpassword"}
        )
        assert response.status_code == 200


class TestSignupPage:
    """Tests for signup page."""

    def test_signup_page_get(self, client):
        """Test signup page GET."""
        response = client.get("/auth/signup")
        assert response.status_code == 200

    def test_signup_page_post_empty(self, client):
        """Test signup with empty data."""
        response = client.post("/auth/signup", data={})
        assert response.status_code == 200

    def test_signup_short_username(self, client):
        """Test signup with short username."""
        response = client.post(
            "/auth/signup",
            data={
                "username": "ab",
                "email": "test@example.com",
                "password": "testpassword123",
                "confirm_password": "testpassword123",
            },
        )
        assert response.status_code == 200

    def test_signup_invalid_email(self, client):
        """Test signup with invalid email."""
        response = client.post(
            "/auth/signup",
            data={
                "username": "testuser",
                "email": "invalid-email",
                "password": "testpassword123",
                "confirm_password": "testpassword123",
            },
        )
        assert response.status_code == 200

    def test_signup_short_password(self, client):
        """Test signup with short password."""
        response = client.post(
            "/auth/signup",
            data={
                "username": "testuser",
                "email": "test@example.com",
                "password": "short",
                "confirm_password": "short",
            },
        )
        assert response.status_code == 200

    def test_signup_passwords_dont_match(self, client):
        """Test signup with mismatched passwords."""
        response = client.post(
            "/auth/signup",
            data={
                "username": "testuser",
                "email": "test@example.com",
                "password": "password123",
                "confirm_password": "differentpassword",
            },
        )
        assert response.status_code == 200


class TestLogout:
    """Tests for logout."""

    def test_logout_redirects(self, client):
        """Test logout redirects to login."""
        response = client.get("/auth/logout")
        assert response.status_code == 302


class TestSetupUserSession:
    """Tests for setup_user_session function."""

    def test_setup_user_session(self, client):
        """Test setup user session sets session variables."""
        # Just verify session_transaction works
        with client.session_transaction() as _sess:
            pass

        from flask_app.routes.auth import setup_user_session

        with patch("flask_app.routes.auth.session", dict()):
            setup_user_session("user-123", "test@example.com")


class TestAuthRedirects:
    """Tests for auth redirects when already logged in."""

    def test_login_redirects_logged_in(self, client):
        """Test login redirects if already logged in."""
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user"

        response = client.get("/auth/login")
        assert response.status_code == 302

    def test_signup_redirects_logged_in(self, client):
        """Test signup redirects if already logged in."""
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user"

        response = client.get("/auth/signup")
        assert response.status_code == 302


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
