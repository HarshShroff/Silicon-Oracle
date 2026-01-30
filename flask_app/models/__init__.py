"""
Silicon Oracle - Database Models
All models for the application.
"""

from datetime import datetime


class User:
    """
    User Model with API Keys Storage

    Stores user credentials and their personal API keys for various services.
    Each user's API keys are isolated and only accessible to them.
    """

    def __init__(self, id, username, email, password):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password  # Supabase handles hashing
        self.finnhub_api_key = None
        self.alpaca_api_key = None
        self.alpaca_secret_key = None
        self.gemini_api_key = None
        self.email_notifications = True
        self.sms_notifications = False
        self.phone_number = None
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.last_login = None
        self.is_authenticated = False  # Default to False

    def set_password(self, password):
        """Hash and set the password."""
        self.password_hash = password  # Supabase handles hashing

    def check_password(self, password):
        """Check the password against the hash."""
        # This will be handled by Supabase client
        return True

    def get_api_keys(self):
        """Return a dict of user's API keys for service initialization."""
        return {
            "FINNHUB_API_KEY": self.finnhub_api_key or "",
            "ALPACA_API_KEY": self.alpaca_api_key or "",
            "ALPACA_SECRET_KEY": self.alpaca_secret_key or "",
            "GEMINI_API_KEY": self.gemini_api_key or "",
        }

    def has_required_keys(self):
        """Check if user has at least the essential API keys configured."""
        return bool(self.finnhub_api_key)

    def to_dict(self):
        """Convert to dictionary for API responses (excludes sensitive data)."""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "has_finnhub_key": bool(self.finnhub_api_key),
            "has_alpaca_keys": bool(self.alpaca_api_key and self.alpaca_secret_key),
            "has_gemini_key": bool(self.gemini_api_key),
            "email_notifications": self.email_notifications,
            "sms_notifications": self.sms_notifications,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<User {self.username}>"
