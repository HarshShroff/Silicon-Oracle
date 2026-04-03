"""
Silicon Oracle - Flask Configuration
Production-grade configuration management
"""

import os
from datetime import timedelta
from urllib.parse import quote_plus, urlparse, urlunparse


def load_streamlit_secrets():
    """Load API keys from .streamlit/secrets.toml if available."""
    secrets = {}
    secrets_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), ".streamlit", "secrets.toml"
    )

    if os.path.exists(secrets_path):
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                # Fallback: simple TOML parsing for basic cases
                try:
                    with open(secrets_path, "r") as f:
                        content = f.read()
                        # Parse basic TOML format
                        current_section = None
                        for line in content.split("\n"):
                            line = line.strip()
                            if line.startswith("[") and line.endswith("]"):
                                current_section = line[1:-1]
                            elif "=" in line and not line.startswith("#"):
                                key, value = line.split("=", 1)
                                key = key.strip()
                                value = value.strip().strip('"').strip("'")
                                if current_section:
                                    secrets[f"{current_section}.{key}"] = value
                    return secrets
                except Exception:
                    return secrets

        try:
            with open(secrets_path, "rb") as f:
                data = tomllib.load(f)
                # Flatten nested structure
                for section, values in data.items():
                    if isinstance(values, dict):
                        for key, value in values.items():
                            secrets[f"{section}.{key}"] = value
        except Exception:
            pass

    return secrets


# Load secrets once at module level
_streamlit_secrets = load_streamlit_secrets()


def get_secret(env_key, secrets_key, default=""):
    """Get a secret from environment or secrets.toml."""
    return os.environ.get(env_key) or _streamlit_secrets.get(secrets_key, default)


def fix_database_url(db_url: str) -> str:
    """
    Fix and properly encode database URL to handle special characters in passwords.

    Args:
        db_url: Database connection string

    Returns:
        Properly formatted and encoded database URL
    """
    if not db_url:
        return db_url

    # Handle Heroku-style postgres:// to postgresql:// conversion
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    try:
        # Parse the URL to extract components
        parsed = urlparse(db_url)

        # If there's a password in the URL, ensure it's properly encoded
        if parsed.password:
            # The password might already be URL-encoded or might need encoding
            # We'll decode first (if it's already encoded) then re-encode to ensure consistency
            try:
                from urllib.parse import unquote

                # Try to detect if it's already encoded by checking for %
                # If decoding changes it, it was encoded; if not, it wasn't
                decoded_pass = unquote(parsed.password)

                # Re-encode the password properly
                encoded_pass = quote_plus(decoded_pass)

                # Reconstruct the URL with properly encoded password
                netloc = parsed.netloc
                if "@" in netloc:
                    # Split user info from host
                    userinfo, host = netloc.rsplit("@", 1)
                    if ":" in userinfo:
                        username, _ = userinfo.split(":", 1)
                        # Reconstruct with encoded password
                        netloc = f"{username}:{encoded_pass}@{host}"

                    # Reconstruct the full URL
                    db_url = urlunparse(
                        (
                            parsed.scheme,
                            netloc,
                            parsed.path,
                            parsed.params,
                            parsed.query,
                            parsed.fragment,
                        )
                    )
            except Exception:
                # If any error occurs during encoding, return original
                pass

    except Exception:
        # If parsing fails, return the original URL
        pass

    return db_url


class Config:
    """Base configuration."""

    # Flask
    SECRET_KEY = os.environ.get("SECRET_KEY", "silicon-oracle-dev-key-change-in-production")

    # API Keys (BYOK - Bring Your Own Keys)
    ALPACA_API_KEY = get_secret("ALPACA_API_KEY", "alpaca.api_key", "")
    ALPACA_SECRET_KEY = get_secret("ALPACA_SECRET_KEY", "alpaca.secret_key", "")
    FINNHUB_API_KEY = get_secret("FINNHUB_API_KEY", "finnhub.api_key", "")
    GEMINI_API_KEY = get_secret("GEMINI_API_KEY", "gemini.api_key", "")

    # Supabase (optional)
    SUPABASE_URL = get_secret("SUPABASE_URL", "supabase.url", "")
    SUPABASE_ANON_KEY = get_secret("SUPABASE_ANON_KEY", "supabase.anon_key", "")

    # Database - Priority order:
    # 1. DATABASE_URL env var (can be Supabase PostgreSQL connection string)
    # 2. SUPABASE_DB_URL for direct PostgreSQL connection
    # 3. Local SQLite fallback
    #
    # To use Supabase:
    # Set DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT-ID].supabase.co:5432/postgres
    # Or set SUPABASE_DB_URL with the same format
    SUPABASE_DB_URL = get_secret("SUPABASE_DB_URL", "supabase.db_url", "")

    # Check for database URL in order of priority
    _db_url = os.environ.get("DATABASE_URL", "")

    # Apply database URL fixes (encoding, protocol conversion, etc.)
    _db_url = fix_database_url(_db_url)
    _supabase_db_url = fix_database_url(SUPABASE_DB_URL)

    if _db_url:
        SQLALCHEMY_DATABASE_URI = _db_url
    elif _supabase_db_url:
        SQLALCHEMY_DATABASE_URI = _supabase_db_url
    else:
        # Fallback to local SQLite database
        SQLALCHEMY_DATABASE_URI = "sqlite:///portfolio.db"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    # Use cookie-based sessions (default) instead of filesystem for cloud deployments
    # SESSION_TYPE = "filesystem"  # Don't use filesystem on ephemeral cloud platforms

    # Cache
    CACHE_TYPE = "simple"
    CACHE_DEFAULT_TIMEOUT = 300

    # Rate limiting
    RATELIMIT_DEFAULT = "100 per minute"
    RATELIMIT_STORAGE_URL = "memory://"

    # Scheduler
    SCHEDULER_API_ENABLED = True


class DevelopmentConfig(Config):
    """Development configuration."""

    DEBUG = True
    TESTING = False

    # Secure cookie settings (even in dev, use reasonable defaults)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Only set secure=True in production to avoid cookie rejection on localhost
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV", "").lower() == "production"


class ProductionConfig(Config):
    """Production configuration."""

    DEBUG = False
    TESTING = False

    # Stronger session security
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Don't expose scheduler job-management API in production
    SCHEDULER_API_ENABLED = False


class TestingConfig(Config):
    """Testing configuration."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
