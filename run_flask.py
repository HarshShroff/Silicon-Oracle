#!/usr/bin/env python3
"""
Silicon Oracle - Flask Application Runner
Run this to start the Flask web application.

Usage:
    python run_flask.py

The app will be available at: http://localhost:5001
"""

import os
import sys

from flask_app import create_app

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env file if it exists
try:
    from dotenv import load_dotenv

    load_dotenv()
    print("✓ Loaded environment variables from .env")
except ImportError:
    print("⚠ python-dotenv not installed. Install with: pip install python-dotenv")
    print("  Continuing without .env file...")
except Exception as e:
    print(f"⚠ Could not load .env file: {e}")


# Create the Flask application
# Load secrets into environment variables for shared utilities
try:
    from flask_app.config import load_streamlit_secrets

    secrets = load_streamlit_secrets()

    # Map specifically Supabase keys for utils.database
    if "supabase.url" in secrets and "SUPABASE_URL" not in os.environ:
        os.environ["SUPABASE_URL"] = secrets["supabase.url"]
    if "supabase.anon_key" in secrets and "SUPABASE_ANON_KEY" not in os.environ:
        os.environ["SUPABASE_ANON_KEY"] = secrets["supabase.anon_key"]

    # Map other API keys if needed by services
    if "alpaca.api_key" in secrets and "ALPACA_API_KEY" not in os.environ:
        os.environ["ALPACA_API_KEY"] = secrets["alpaca.api_key"]
    if "alpaca.secret_key" in secrets and "ALPACA_SECRET_KEY" not in os.environ:
        os.environ["ALPACA_SECRET_KEY"] = secrets["alpaca.secret_key"]

except Exception as e:
    print(f"Warning: Could not load secrets into environment: {e}")

app = create_app(os.environ.get("FLASK_ENV", "development"))

if __name__ == "__main__":
    # Run the development server
    # Note: Use gunicorn for production deployment
    is_production = os.environ.get("FLASK_ENV") == "production"
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5001)),
        debug=not is_production,
        threaded=True,
    )
