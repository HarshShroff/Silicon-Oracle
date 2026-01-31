"""
Silicon Oracle - Flask Application Factory
AI-Powered Stock Analysis & Paper Trading Platform
"""

from flask_app.extensions import cache, csrf
import os
import sys
from flask import Flask, g, session, request, redirect, url_for, flash
from werkzeug.datastructures import ImmutableMultiDict

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def create_app(config_name=None):
    """Application factory for Flask app."""

    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    # Normalize config name to lowercase to handle case variations
    config_name = config_name.lower()

    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Load configuration
    from flask_app.config import config
    app.config.from_object(config[config_name])

    # Initialize extensions with app
    cache.init_app(app)
    csrf.init_app(app)

    # Register blueprints
    from flask_app.routes.main import main_bp
    from flask_app.routes.api import api_bp
    from flask_app.routes.auth import auth_bp
    from flask_app.routes.sentinel import sentinel_bp
    from flask_app.routes.sentinel_ui import sentinel_ui_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(sentinel_bp, url_prefix="/sentinel")
    app.register_blueprint(sentinel_ui_bp)

    # Exempt API routes from CSRF
    csrf.exempt(api_bp)
    csrf.exempt(sentinel_bp)
    csrf.exempt(sentinel_ui_bp)

    # Initialize Scheduler
    try:
        from flask_app.scheduler import scheduler, init_scheduler
        if not scheduler.running:
            scheduler.init_app(app)
            init_scheduler(app)
            scheduler.start()
    except Exception as e:
        app.logger.warning(f"Scheduler initialization failed: {e}")

    # ============================================
    # MIDDLEWARE (ORDER MATTERS)
    # ============================================

    @app.before_request
    def load_logged_in_user():
        """1. Load identity first so subsequent checks know who the user is."""
        from utils import database as db
        from flask_app.models import User

        user_id = session.get('user_id')
        g.user = None

        if user_id:
            profile = db.get_user_profile(user_id)
            if profile:
                user_api_keys = db.get_user_api_keys(user_id, decrypt=True)

                display_name = profile.get('username') or profile.get(
                    'email', 'User').split('@')[0]
                g.user = User(
                    id=profile['id'],
                    username=display_name,
                    email=profile.get('email'),
                    password=None
                )

                g.user.finnhub_api_key = user_api_keys.get(
                    'FINNHUB_API_KEY', '')
                g.user.alpaca_api_key = user_api_keys.get('ALPACA_API_KEY', '')
                g.user.alpaca_secret_key = user_api_keys.get(
                    'ALPACA_SECRET_KEY', '')
                g.user.gemini_api_key = user_api_keys.get('GEMINI_API_KEY', '')
                g.user.is_authenticated = True
            else:
                session.clear()

    @app.before_request
    def normalize_ticker_params():
        """2. Clean up input parameters."""
        if request.view_args and 'ticker' in request.view_args:
            ticker = request.view_args['ticker']
            if '.' in ticker:
                request.view_args['ticker'] = ticker.replace('.', '-')

        if request.args:
            new_args = {}
            for key, value in request.args.items():
                if key == 'ticker' or key.endswith('_ticker'):
                    new_args[key] = value.replace(
                        '.', '-') if '.' in value else value
                else:
                    new_args[key] = value
            request.args = ImmutableMultiDict(new_args)

    @app.before_request
    def check_api_keys():
        """3. Enforce API key requirements after identity is known."""
        if request.endpoint and (
            request.endpoint.startswith('auth.') or
            request.endpoint.startswith('static') or
            request.endpoint.startswith('api.') or
            request.endpoint.startswith('sentinel_ui.') or
            request.endpoint.startswith('sentinel.') or
            request.endpoint == 'main.settings' or
            request.path.startswith('/api/') or
            request.path.startswith('/sentinel/')
        ):
            return

        if hasattr(g, 'user') and g.user and g.user.is_authenticated:
            user_keys = g.user.get_api_keys()
            has_finnhub = bool(user_keys.get('FINNHUB_API_KEY'))

            if not has_finnhub:
                session['redirect_after_setup'] = request.url
                flash(
                    '⚠️ Please add your Finnhub API key to continue. It\'s required for market data.', 'warning')
                return redirect(url_for('main.settings'))

            has_alpaca = bool(user_keys.get('ALPACA_API_KEY'))
            has_gemini = bool(user_keys.get('GEMINI_API_KEY'))

            if not has_alpaca and request.endpoint in ['main.portfolio', 'main.trade']:
                flash(
                    'ℹ️ Add Alpaca API keys in Settings to enable live trading.', 'info')

            if not has_gemini and request.endpoint == 'main.analysis':
                flash('ℹ️ Add Gemini API key in Settings to enable AI analysis.', 'info')

    # Context processors
    @app.context_processor
    def inject_globals():
        return {
            'app_name': 'Silicon Oracle',
            'app_version': '2.0',
            'current_user': g.user if hasattr(g, 'user') and g.user else None
        }

    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return {"error": "Not found"}, 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"Internal error: {error}")
        return {"error": "Internal server error"}, 500

    return app
