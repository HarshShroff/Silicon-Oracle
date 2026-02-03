"""
Silicon Oracle - API Routes
RESTful API endpoints for AJAX calls
"""

import logging
import numpy as np
from datetime import datetime
from flask import Blueprint, jsonify, request, session, g
from flask_app.services import (
    StockService,
    OracleService,
    ScannerService,
    TradingService,
    PortfolioService,
)
from flask_app.services.enhanced_oracle_service import EnhancedOracleService
from flask_app.services.notifications_service import (
    send_price_alert,
    send_ai_signal_alert,
    send_position_alert,
    send_daily_digest,
    test_email_config,
)
from flask_app.services.scanner_service import WATCHLISTS
from flask_app.extensions import cache

logger = logging.getLogger(__name__)
api_bp = Blueprint("api", __name__)


@api_bp.route("/oracle/insight/<ticker>")
@cache.memoize(timeout=3600)
def get_oracle_insight(ticker):
    """Get snappy Gemini AI insight for a ticker. Cached for 1 hour."""
    from flask_app.services.gemini_service import GeminiService
    from utils.ticker_utils import normalize_ticker

    config = get_config()
    if not config.get("GEMINI_API_KEY"):
        return jsonify({"insight": "Gemini Key Required", "locked": True})

    gemini_service = GeminiService(config)
    insight = gemini_service.get_quick_insight(normalize_ticker(ticker))

    return jsonify({"insight": insight, "locked": False})


@api_bp.errorhandler(Exception)
def handle_api_error(error):
    """Global error handler for API routes."""
    logger.error(f"API Error: {error}")
    return jsonify({"error": str(error)}), 500


def get_config():
    """Get API config from current user ONLY - no fallback to app config."""
    from flask import g

    # ONLY use authenticated user's API keys from database
    # NO fallback to secrets.toml - users MUST add their own keys
    if hasattr(g, 'user') and g.user and g.user.is_authenticated:
        user_keys = g.user.get_api_keys()
        if user_keys:
            return user_keys

    # Return empty config - user must add their own keys
    return {
        "FINNHUB_API_KEY": "",
        "ALPACA_API_KEY": "",
        "ALPACA_SECRET_KEY": "",
        "GEMINI_API_KEY": "",
    }


def get_trading_style():
    """Get the current user's trading style from simulation settings."""
    from utils import database as db

    user_id = g.user.id if hasattr(g, 'user') and g.user else session.get("user_id")
    if user_id:
        sim_settings = db.get_simulation_settings(user_id)
        if sim_settings:
            return sim_settings.get("trading_style", "swing_trading")
    return "swing_trading"


# ============================================
# STOCK DATA ENDPOINTS
# ============================================


@api_bp.route("/stock/<ticker>")
def get_stock(ticker):
    """Get complete stock data."""
    from utils.ticker_utils import normalize_ticker
    stock_service = StockService(get_config())
    data = stock_service.get_complete_data(normalize_ticker(ticker))
    return jsonify(data)


@api_bp.route("/stock/<ticker>/quote")
def get_quote(ticker):
    """Get real-time quote."""
    from utils.ticker_utils import normalize_ticker
    stock_service = StockService(get_config())
    quote = stock_service.get_realtime_quote(normalize_ticker(ticker))
    return jsonify(quote or {"error": "No data"})


@api_bp.route("/stock/<ticker>/chart")
def get_chart_data(ticker):
    """Get historical chart data."""
    from utils.ticker_utils import normalize_ticker
    period = request.args.get("period", "1y")
    interval = request.args.get("interval", "1d")

    stock_service = StockService(get_config())
    df = stock_service.get_historical_data(
        normalize_ticker(ticker), period, interval)

    if df is not None:
        data = df.reset_index().to_dict(orient="records")
        # Convert timestamps to strings
        for row in data:
            if "Date" in row:
                row["Date"] = str(row["Date"])
            if "Datetime" in row:
                row["Datetime"] = str(row["Datetime"])
        return jsonify(data)
    return jsonify([])


@api_bp.route("/stock/<ticker>/news")
def get_news(ticker):
    """Get stock news."""
    from utils.ticker_utils import normalize_ticker
    stock_service = StockService(get_config())
    news = stock_service.get_news(normalize_ticker(ticker))
    return jsonify(news)


@api_bp.route("/stock/<ticker>/analysis")
def get_analysis(ticker):
    """Get complete stock analysis data."""
    from utils.ticker_utils import normalize_ticker
    oracle_service = OracleService(get_config())
    data = oracle_service.stock_service.get_complete_data(
        normalize_ticker(ticker))

    # Convert to serializable format
    result = {}

    # Quote data
    if hasattr(data, "quote") and data.quote is not None:
        result["quote"] = (
            data.quote.__dict__ if hasattr(
                data.quote, "__dict__") else data.quote
        )

    # Company data
    if hasattr(data, "company") and data.company is not None:
        result["company"] = (
            data.company.__dict__ if hasattr(
                data.company, "__dict__") else data.company
        )

    # Technicals
    if hasattr(data, "technicals") and data.technicals is not None:
        result["technicals"] = (
            data.technicals.__dict__
            if hasattr(data.technicals, "__dict__")
            else data.technicals
        )

    # News
    if hasattr(data, "news") and data.news is not None:
        result["news"] = data.news

    # Peers
    if hasattr(data, "peers") and data.peers is not None:
        result["peers"] = data.peers

    # Earnings
    if hasattr(data, "earnings") and data.earnings is not None:
        result["earnings"] = (
            data.earnings.__dict__
            if hasattr(data.earnings, "__dict__")
            else data.earnings
        )

    return jsonify(result)


@api_bp.route("/stock/<ticker>/ai-analysis")
def get_ai_analysis(ticker):
    """Get AI Deep Dive analysis, tailored to the user's trading style."""
    from flask_app.services.gemini_service import GeminiService
    from utils.ticker_utils import normalize_ticker

    gemini_service = GeminiService(get_config())
    html, score, label = gemini_service.analyze_ticker(
        normalize_ticker(ticker), trading_style=get_trading_style())

    return jsonify({
        "html": html,
        "score": score,
        "label": label
    })


@api_bp.route("/market/status")
def market_status():
    """Get market status."""
    stock_service = StockService(get_config())
    return jsonify(stock_service.get_market_status())


# ============================================
# ORACLE ENDPOINTS
# ============================================


@api_bp.route("/oracle/<ticker>")
def get_oracle(ticker):
    """Get enhanced Oracle analysis for a ticker."""
    from utils.ticker_utils import normalize_ticker
    oracle_service = EnhancedOracleService(get_config())
    result = oracle_service.calculate_enhanced_oracle_score(
        normalize_ticker(ticker))
    return jsonify(result)


@api_bp.route("/oracle/scan", methods=["POST"])
def oracle_scan():
    """Scan multiple tickers with enhanced Oracle."""
    data = request.get_json()
    tickers = data.get("tickers", [])

    if not tickers:
        return jsonify({"error": "No tickers provided"}), 400

    oracle_service = EnhancedOracleService(get_config())
    results = oracle_service.scan_watchlist(tickers)
    return jsonify(results)


@api_bp.route("/scanner/volume-spikes")
def get_volume_spikes():
    """Detect volume spikes for watchlist."""
    watchlist = request.args.get("watchlist", "AI/Tech")
    tickers = WATCHLISTS.get(watchlist, [])

    if not tickers:
        return jsonify([])

    oracle_service = EnhancedOracleService(get_config())
    spikes = oracle_service.detect_volume_spikes(tickers)
    return jsonify(spikes)


@api_bp.route("/scanner/relative-strength")
def get_relative_strength():
    """Calculate relative strength vs SPY."""
    watchlist = request.args.get("watchlist", "AI/Tech")
    tickers = WATCHLISTS.get(watchlist, [])

    if not tickers:
        return jsonify([])

    oracle_service = EnhancedOracleService(get_config())
    strength = oracle_service.get_relative_strength(tickers)
    return jsonify(strength)


@api_bp.route("/oracle/ai-interpretation/<ticker>")
def get_oracle_ai_interpretation(ticker):
    """Get AI interpretation of Oracle factors, framed for the user's trading style."""
    from flask_app.services.gemini_service import GeminiService
    from utils.ticker_utils import normalize_ticker

    ticker = normalize_ticker(ticker)

    # Get Oracle score first
    oracle_service = EnhancedOracleService(get_config())
    oracle_data = oracle_service.calculate_enhanced_oracle_score(ticker)

    # Get AI interpretation with trading style context
    gemini_service = GeminiService(get_config())
    interpretation = gemini_service.get_factor_interpretation(
        ticker, oracle_data, trading_style=get_trading_style())

    if interpretation == "Gemini API Key Required":
        return jsonify({"locked": True, "interpretation": None})

    return jsonify({"locked": False, "interpretation": interpretation})


@api_bp.route("/oracle/pattern-analysis/<ticker>")
def get_oracle_pattern_analysis(ticker):
    """Get AI pattern analysis for a ticker."""
    from flask_app.services.gemini_service import GeminiService
    from utils.ticker_utils import normalize_ticker

    gemini_service = GeminiService(get_config())
    pattern_analysis = gemini_service.get_pattern_analysis(
        normalize_ticker(ticker))

    if pattern_analysis == "Gemini API Key Required":
        return jsonify({"locked": True, "pattern_analysis": None})

    return jsonify({"locked": False, "pattern_analysis": pattern_analysis})


# ============================================
# SCANNER ENDPOINTS
# ============================================


@api_bp.route("/scanner/watchlists")
def get_watchlists():
    """Get available watchlists including user watchlists."""
    user_lists = session.get("user_watchlists", {})

    # Combine predefined watchlists with user watchlists
    all_watchlists = []

    # Add predefined watchlists
    for name, tickers in WATCHLISTS.items():
        all_watchlists.append(
            {"name": name, "tickers": tickers, "type": "predefined"})

    # Add user watchlists
    for name, data in user_lists.items():
        all_watchlists.append({
            "name": name,
            "tickers": data["tickers"],
            "type": "user",
            "created_at": data.get("created_at"),
        })

    return jsonify(all_watchlists)


@api_bp.route("/scanner/watchlists/create", methods=["POST"])
def create_watchlist():
    """Create a new watchlist."""
    data = request.get_json()
    name = data.get("name")
    tickers = data.get("tickers", [])

    if not name or not tickers:
        return jsonify({"error": "Name and tickers required"}), 400

    # For now, store in session (later: store in database)
    if "user_watchlists" not in session:
        session["user_watchlists"] = {}

    session["user_watchlists"][name] = {
        "name": name,
        "tickers": tickers,
        "created_at": datetime.now().isoformat(),
    }

    return jsonify({"success": True, "watchlist": session["user_watchlists"][name]})


@api_bp.route("/scanner/watchlists/<name>", methods=["DELETE"])
def delete_watchlist(name):
    """Delete a watchlist."""
    if "user_watchlists" in session and name in session["user_watchlists"]:
        del session["user_watchlists"][name]
        return jsonify({"success": True})

    return jsonify({"error": "Watchlist not found"}), 404


@api_bp.route("/scanner/watchlists/add-ticker", methods=["POST"])
def add_ticker_to_watchlist():
    """Add ticker to watchlist."""
    data = request.get_json()
    name = data.get("name")
    ticker = data.get("ticker")

    if not name or not ticker:
        return jsonify({"error": "Name and ticker required"}), 400

    if "user_watchlists" not in session or name not in session["user_watchlists"]:
        return jsonify({"error": "Watchlist not found"}), 404

    ticker = ticker.upper()
    if ticker not in session["user_watchlists"][name]["tickers"]:
        session["user_watchlists"][name]["tickers"].append(ticker)

    return jsonify({"success": True})


@api_bp.route("/scanner/watchlists/remove-ticker", methods=["POST"])
def remove_ticker_from_watchlist():
    """Remove ticker from watchlist."""
    data = request.get_json()
    name = data.get("name")
    ticker = data.get("ticker")

    if not name or not ticker:
        return jsonify({"error": "Name and ticker required"}), 400

    if "user_watchlists" not in session or name not in session["user_watchlists"]:
        return jsonify({"error": "Watchlist not found"}), 404

    ticker = ticker.upper()
    if ticker in session["user_watchlists"][name]["tickers"]:
        session["user_watchlists"][name]["tickers"].remove(ticker)

    return jsonify({"success": True})


@api_bp.route("/scanner/scan", methods=["POST"])
def run_scan():
    """Run scanner on tickers."""
    data = request.get_json()
    tickers = data.get("tickers", [])

    if not tickers:
        return jsonify({"error": "No tickers provided"}), 400

    scanner_service = ScannerService(get_config())
    results = scanner_service.scan_watchlist(tickers)
    return jsonify(results)


# ============================================
# TRADING ENDPOINTS
# ============================================


@api_bp.route("/trading/account")
def get_account():
    """Get Alpaca account info."""
    trading_service = TradingService(get_config())
    if not trading_service.is_connected():
        return jsonify({"error": "Not connected to Alpaca"}), 401

    account = trading_service.get_account()
    return jsonify(account or {"error": "Failed to get account"})


@api_bp.route("/trading/positions")
def get_positions():
    """Get all positions."""
    trading_service = TradingService(get_config())
    if not trading_service.is_connected():
        return jsonify([])

    return jsonify(trading_service.get_positions())


@api_bp.route("/trading/orders")
def get_orders():
    """Get orders."""
    status = request.args.get("status", "open")
    trading_service = TradingService(get_config())
    return jsonify(trading_service.get_orders(status=status))


@api_bp.route("/trading/order", methods=["POST"])
def submit_order():
    """Submit a new order."""
    data = request.get_json()

    ticker = data.get("ticker")
    qty = data.get("qty")
    side = data.get("side")
    order_type = data.get("order_type", "market")
    limit_price = data.get("limit_price")

    if not all([ticker, qty, side]):
        return jsonify({"error": "Missing required fields"}), 400

    trading_service = TradingService(get_config())
    if not trading_service.is_connected():
        return jsonify({"error": "Not connected to Alpaca"}), 401

    result = trading_service.submit_order(
        ticker, float(qty), side, order_type, limit_price
    )

    # Log trade to local DB
    if result.get("success") and hasattr(g, 'user') and g.user:
        portfolio_service = PortfolioService(g.user.id)
        stock_service = StockService(get_config())
        quote = stock_service.get_realtime_quote(ticker)
        price = quote.get("current", 0) if quote else 0
        portfolio_service.add_trade(
            ticker, side, float(qty), price, "Alpaca", result.get(
                "order_id"), "alpaca"
        )

    return jsonify(result)


@api_bp.route("/trading/order/<order_id>", methods=["DELETE"])
def cancel_order(order_id):
    """Cancel an order."""
    trading_service = TradingService(get_config())
    result = trading_service.cancel_order(order_id)
    return jsonify(result)


@api_bp.route("/trading/position/<ticker>", methods=["DELETE"])
def close_position(ticker):
    """Close a position."""
    trading_service = TradingService(get_config())
    result = trading_service.close_position(ticker)
    return jsonify(result)


@api_bp.route("/trading/history")
def portfolio_history():
    """Get portfolio value history."""
    period = request.args.get("period", "1M")
    timeframe = request.args.get("timeframe", "1D")
    trading_service = TradingService(get_config())
    df = trading_service.get_portfolio_history(
        period=period, timeframe=timeframe)

    if df is not None:
        data = df.to_dict(orient="records")
        for row in data:
            row["timestamp"] = str(row["timestamp"])
        return jsonify(data)
    return jsonify([])


@api_bp.route("/trading/watchlists")
def get_alpaca_watchlists():
    """Get Alpaca watchlists."""
    trading_service = TradingService(get_config())
    if not trading_service.is_connected():
        return jsonify([])
    return jsonify(trading_service.get_watchlists())


@api_bp.route("/trading/watchlists/<watchlist_id>", methods=["DELETE"])
def delete_alpaca_watchlist(watchlist_id):
    """Delete an Alpaca watchlist."""
    trading_service = TradingService(get_config())
    if not trading_service.is_connected():
        return jsonify({"error": "Not connected"}), 401

    try:
        trading_service.trading_client.delete_watchlist(watchlist_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/trading/watchlists/<watchlist_id>/sync", methods=["POST"])
def sync_alpaca_watchlist(watchlist_id):
    """Sync watchlist from Alpaca to local."""
    trading_service = TradingService(get_config())
    if not trading_service.is_connected():
        return jsonify({"error": "Not connected"}), 401

    try:
        watchlists = trading_service.get_watchlists()
        wl = next((w for w in watchlists if w["id"] == watchlist_id), None)
        if wl:
            return jsonify({"success": True, "watchlist": wl})
        return jsonify({"error": "Watchlist not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/trading/watchlists/sync-local", methods=["POST"])
def sync_local_to_alpaca():
    """Sync a local watchlist to Alpaca."""
    data = request.get_json()
    name = data.get("name")
    tickers = data.get("tickers", [])

    if not name:
        return jsonify({"error": "Name required"}), 400

    trading_service = TradingService(get_config())
    if not trading_service.is_connected():
        return jsonify({"error": "Not connected to Alpaca"}), 401

    try:
        result = trading_service.create_watchlist(name, tickers)
        if result:
            return jsonify({"success": True, "watchlist": result})
        return jsonify({"error": "Failed to create watchlist"}), 500
    except Exception as e:
        # Watchlist may already exist, try updating
        try:
            from alpaca.trading.requests import UpdateWatchlistRequest
            watchlists = trading_service.get_watchlists()
            existing = next((w for w in watchlists if w["name"] == name), None)
            if existing:
                req = UpdateWatchlistRequest(symbols=tickers)
                trading_service.trading_client.update_watchlist_by_id(
                    existing["id"], req)
                return jsonify({"success": True, "message": "Updated existing watchlist"})
        except Exception as update_error:
            logger.error(f"Error updating watchlist: {update_error}")
        return jsonify({"error": str(e)}), 500


# ============================================
# PORTFOLIO ENDPOINTS
# ============================================


@api_bp.route("/portfolio/trades")
def get_trades():
    """Get trade history for current user."""
    if not hasattr(g, 'user') or not g.user:
        return jsonify([])
    limit = request.args.get("limit", 50, type=int)
    portfolio_service = PortfolioService(g.user.id)
    return jsonify(portfolio_service.get_trade_history(limit))


@api_bp.route("/portfolio/metrics")
def get_metrics():
    """Get performance metrics for current user."""
    if not hasattr(g, 'user') or not g.user:
        return jsonify({})
    portfolio_service = PortfolioService(g.user.id)
    return jsonify(portfolio_service.get_performance_metrics())


@api_bp.route("/portfolio/history")
def account_history():
    """Get account history for current user."""
    if not hasattr(g, 'user') or not g.user:
        return jsonify([])
    portfolio_service = PortfolioService(g.user.id)
    return jsonify(portfolio_service.get_account_history())


# ============================================
# NOTIFICATION ENDPOINTS
# ============================================


@api_bp.route("/notifications/test-email", methods=["POST"])
def test_notification_email():
    """Test email configuration."""
    data = request.get_json()
    email = data.get("email")
    app_password = data.get("app_password")

    if not email or not app_password:
        return jsonify({"error": "Email and app password required"}), 400

    result = test_email_config(email, app_password)
    return jsonify(result)


@api_bp.route("/notifications/price-alert", methods=["POST"])
def send_price_notification():
    """Send price alert notification."""
    data = request.get_json()
    email = data.get("email")
    app_password = data.get("app_password")
    ticker = data.get("ticker")
    current_price = data.get("current_price")
    target_price = data.get("target_price")

    if not all([email, app_password, ticker, current_price, target_price]):
        return jsonify({"error": "Missing required fields"}), 400

    result = send_price_alert(
        email, app_password, ticker, current_price, target_price)
    return jsonify(result)


@api_bp.route("/notifications/ai-signal", methods=["POST"])
def send_ai_signal_notification():
    """Send AI signal alert notification."""
    data = request.get_json()
    email = data.get("email")
    app_password = data.get("app_password")
    ticker = data.get("ticker")
    verdict = data.get("verdict")
    score = data.get("score")
    reasons = data.get("reasons", [])

    if not all([email, app_password, ticker, verdict, score is not None]):
        return jsonify({"error": "Missing required fields"}), 400

    result = send_ai_signal_alert(
        email, app_password, ticker, verdict, score, reasons)
    return jsonify(result)


@api_bp.route("/notifications/position-alert", methods=["POST"])
def send_position_notification():
    """Send position alert notification."""
    data = request.get_json()
    email = data.get("email")
    app_password = data.get("app_password")
    ticker = data.get("ticker")
    action = data.get("action")
    pnl_amount = data.get("pnl_amount")
    pnl_percent = data.get("pnl_percent")

    if not all(
        [
            email,
            app_password,
            ticker,
            action,
            pnl_amount is not None,
            pnl_percent is not None,
        ]
    ):
        return jsonify({"error": "Missing required fields"}), 400

    result = send_position_alert(
        email, app_password, ticker, action, pnl_amount, pnl_percent
    )
    return jsonify(result)


@api_bp.route("/notifications/daily-digest", methods=["POST"])
def send_daily_digest_notification():
    """Send daily digest notification."""
    data = request.get_json()
    email = data.get("email")
    app_password = data.get("app_password")
    portfolio_summary = data.get("portfolio_summary", {})
    top_opportunities = data.get("top_opportunities", [])
    market_status = data.get("market_status", {})

    if not all([email, app_password]):
        return jsonify({"error": "Email and app password required"}), 400

    result = send_daily_digest(
        email, app_password, portfolio_summary, top_opportunities, market_status
    )
    return jsonify(result)


# ============================================
# SETTINGS ENDPOINTS
# ============================================


@api_bp.route("/settings/load")
def load_settings():
    """Load user settings from database."""
    from utils import database as db
    if not hasattr(g, 'user') or not g.user:
        return jsonify({"error": "Unauthorized"}), 401

    user_keys = db.get_user_api_keys(g.user.id, decrypt=True)
    notif_prefs = db.get_notification_preferences(g.user.id)

    # Mask keys for display (show last 4 chars only)
    masked_keys = {}
    for key in ["ALPACA_API_KEY", "ALPACA_SECRET_KEY", "FINNHUB_API_KEY", "GEMINI_API_KEY"]:
        value = user_keys.get(key, "")
        if value and len(value) > 4:
            masked_keys[key.lower().replace("_copy", "")] = "***" + value[-4:]
        else:
            masked_keys[key.lower().replace("_copy", "")] = ""

    email_settings = {
        "gmail_address": user_keys.get("GMAIL_ADDRESS", ""),
        "gmail_password": "",  # Never send password back
        "alert_price": notif_prefs.get("price_alerts", False),
        "alert_news": notif_prefs.get("news_alerts", False),
        "alert_daily_digest": notif_prefs.get("daily_digest", False),
    }

    return jsonify({
        "api_keys": masked_keys,
        "email_settings": email_settings
    })


@api_bp.route("/settings/save-api-keys", methods=["POST"])
def save_api_keys():
    """Save API keys to database (BYOK)."""
    from utils import database as db
    if not hasattr(g, 'user') or not g.user:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    api_keys_data = {}

    # Only save if value is provided and not a masked placeholder
    if data.get("alpaca_key") and not data["alpaca_key"].startswith("***"):
        api_keys_data["alpaca_api_key"] = data["alpaca_key"].strip()
    if data.get("alpaca_secret") and not data["alpaca_secret"].startswith("***"):
        api_keys_data["alpaca_secret_key"] = data["alpaca_secret"].strip()
    if data.get("finnhub_key") and not data["finnhub_key"].startswith("***"):
        api_keys_data["finnhub_api_key"] = data["finnhub_key"].strip()
    if data.get("gemini_key") and not data["gemini_key"].startswith("***"):
        api_keys_data["gemini_api_key"] = data["gemini_key"].strip()

    if api_keys_data:
        db.save_user_api_keys(g.user.id, api_keys_data)

    return jsonify({"success": True, "message": "API keys saved to database"})


@api_bp.route("/settings/save-email", methods=["POST"])
def save_email_settings():
    """Save email settings to database."""
    from utils import database as db
    from utils.encryption import encrypt_value

    if not hasattr(g, 'user') or not g.user:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    user_id = g.user.id

    email_data = {
        "gmail_address": data.get("gmail_address", "").strip(),
        "notifications_enabled": True,
    }

    # Only update password if provided and not a masked placeholder
    gmail_password = data.get("gmail_password", "").strip()
    if gmail_password and not gmail_password.startswith("***"):
        email_data["gmail_app_password_encrypted"] = encrypt_value(
            gmail_password)

    # Save notification preferences
    notification_prefs = {
        "price_alerts": data.get("alert_price", False),
        "news_alerts": data.get("alert_news", False) or data.get("alert_positions", False),
        "daily_digest": data.get("alert_daily_digest", False),
        "email_alerts": True,
    }

    db.update_user_profile(user_id, email_data)
    db.update_simulation_settings(user_id, notification_prefs)

    return jsonify({"success": True, "message": "Email settings saved to database"})


@api_bp.route("/settings/test-connections", methods=["POST"])
def test_api_connections():
    """Test API key connections."""
    data = request.get_json()
    results = {}

    # Test Alpaca
    alpaca_key = data.get("alpaca_key") or session.get("alpaca_key")
    alpaca_secret = data.get("alpaca_secret") or session.get("alpaca_secret")

    if alpaca_key and alpaca_secret and not alpaca_key.startswith("***"):
        try:
            from alpaca.trading.client import TradingClient
            client = TradingClient(
                api_key=alpaca_key, secret_key=alpaca_secret, paper=True)
            account = client.get_account()
            results["Alpaca"] = {
                "success": True, "message": f"Connected (${float(account.portfolio_value):,.2f})"}
        except Exception as e:
            results["Alpaca"] = {"success": False, "error": str(e)}
    else:
        results["Alpaca"] = {"success": False,
                             "error": "No credentials provided"}

    # Test Finnhub
    finnhub_key = data.get("finnhub_key") or session.get("finnhub_key")
    if finnhub_key and not finnhub_key.startswith("***"):
        try:
            import requests
            resp = requests.get(
                f"https://finnhub.io/api/v1/quote?symbol=AAPL&token={finnhub_key}", timeout=5)
            if resp.status_code == 200 and resp.json().get("c"):
                results["Finnhub"] = {"success": True, "message": "Connected"}
            else:
                results["Finnhub"] = {"success": False,
                                      "error": "Invalid response"}
        except Exception as e:
            results["Finnhub"] = {"success": False, "error": str(e)}
    else:
        results["Finnhub"] = {"success": False, "error": "No API key provided"}

    # Test Gemini
    gemini_key = data.get("gemini_key") or session.get("gemini_key")
    if gemini_key and not gemini_key.startswith("***"):
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-2.0-flash")
            response = model.generate_content("Say 'Connected' in one word")
            if response.text:
                results["Gemini"] = {"success": True, "message": "Connected"}
            else:
                results["Gemini"] = {"success": False, "error": "No response"}
        except Exception as e:
            results["Gemini"] = {"success": False, "error": str(e)}
    else:
        results["Gemini"] = {"success": False, "error": "No API key provided"}

    return jsonify(results)


@api_bp.route("/settings/data-summary")
def get_data_summary():
    """Get data summary for export section."""
    if not hasattr(g, 'user') or not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    trading_service = TradingService(get_config())
    portfolio_service = PortfolioService(g.user.id)

    # Get counts
    watchlists = len(session.get("user_watchlists", {})) + len(WATCHLISTS)
    positions = len(trading_service.get_positions()
                    ) if trading_service.is_connected() else 0
    trades = len(portfolio_service.get_trade_history(limit=1000))

    return jsonify({
        "watchlists": watchlists,
        "positions": positions,
        "trades": trades,
        "scan_results": session.get("scan_results_count", 0)
    })


@api_bp.route("/settings/export")
def export_data():
    """Export user data as CSV or Excel."""
    if not hasattr(g, 'user') or not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    import io
    from flask import Response

    export_format = request.args.get("format", "csv")
    portfolio_service = PortfolioService(g.user.id)

    # Get trade history
    trades = portfolio_service.get_trade_history(limit=1000)

    if not trades:
        return jsonify({"error": "No data to export"}), 404

    import pandas as pd
    df = pd.DataFrame(trades)

    if export_format == "csv":
        output = io.StringIO()
        df.to_csv(output, index=False)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={
                "Content-Disposition": "attachment;filename=silicon_oracle_export.csv"}
        )
    elif export_format == "excel":
        output = io.BytesIO()
        df.to_excel(output, index=False, engine="openpyxl")
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment;filename=silicon_oracle_export.xlsx"}
        )
    else:
        return jsonify({"error": "Invalid format"}), 400


# ============================================
# NEWS INTELLIGENCE ENDPOINTS
# ============================================


@api_bp.route("/news-intelligence/trigger", methods=["POST"])
def trigger_news_intelligence():
    """
    Manual trigger for news intelligence scan.
    Useful for testing the hourly news digest feature immediately.
    """
    if not hasattr(g, 'user') or not g.user:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        from utils import database as db
        from flask_app.services.news_intelligence_service import NewsIntelligenceService

        user_id = g.user.id
        user_email = g.user.email

        # Get user's API keys
        config = db.get_user_api_keys(user_id, decrypt=True)
        if not config.get("GMAIL_ADDRESS") or not config.get("GMAIL_APP_PASSWORD"):
            return jsonify({
                "error": "Gmail credentials not configured. Please add them in Settings."
            }), 400

        # Add Gmail credentials to config
        config['gmail_address'] = config.get("GMAIL_ADDRESS")
        config['gmail_app_password'] = config.get("GMAIL_APP_PASSWORD")

        # Get user's shadow portfolio holdings
        holdings = db.get_shadow_positions(user_id, is_active=True)
        holding_tickers = [pos.get('ticker')
                           for pos in holdings if pos.get('ticker')]

        logger.info(
            f"Manual news intelligence trigger for {user_email} with {len(holding_tickers)} holdings")

        # Initialize news intelligence service
        news_service = NewsIntelligenceService(config)

        # Get hours_back from request (default 2 hours for manual trigger)
        hours_back = request.json.get('hours_back', 2) if request.json else 2

        # Scan and notify
        sent = news_service.scan_and_notify(
            user_holdings=holding_tickers,
            user_email=user_email,
            include_market_news=True,
            hours_back=hours_back
        )

        if sent:
            return jsonify({
                "success": True,
                "message": f"News intelligence email sent to {user_email}",
                "holdings_count": len(holding_tickers),
                "hours_scanned": hours_back
            })
        else:
            return jsonify({
                "success": False,
                "message": "No important news found in the last {} hour(s)".format(hours_back),
                "holdings_count": len(holding_tickers),
                "hours_scanned": hours_back
            })

    except Exception as e:
        logger.error(
            f"Manual news intelligence trigger failed: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/news-intelligence/status")
def get_news_intelligence_status():
    """
    Get status of news intelligence configuration and last run info.
    """
    if not hasattr(g, 'user') or not g.user:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        from utils import database as db

        user_id = g.user.id

        # Check configuration
        config = db.get_user_api_keys(user_id, decrypt=True)
        prefs = db.get_notification_preferences(user_id)

        # Get holdings count
        holdings = db.get_shadow_positions(user_id, is_active=True)
        holding_tickers = [pos.get('ticker')
                           for pos in holdings if pos.get('ticker')]

        status = {
            "configured": bool(
                config.get("GMAIL_ADDRESS") and
                config.get("GMAIL_APP_PASSWORD") and
                config.get("GEMINI_API_KEY")
            ),
            "news_alerts_enabled": prefs.get("news_alerts", True),
            "notifications_enabled": config.get("notifications_enabled", True),
            "holdings_count": len(holding_tickers),
            "gmail_configured": bool(config.get("GMAIL_ADDRESS") and config.get("GMAIL_APP_PASSWORD")),
            "gemini_configured": bool(config.get("GEMINI_API_KEY")),
            "finnhub_configured": bool(config.get("FINNHUB_API_KEY")),
            "scan_schedule": "Every hour (top of the hour)",
            "missing_config": []
        }

        # Add missing configuration items
        if not config.get("GMAIL_ADDRESS") or not config.get("GMAIL_APP_PASSWORD"):
            status["missing_config"].append(
                "Gmail credentials (required for email alerts)")
        if not config.get("GEMINI_API_KEY"):
            status["missing_config"].append(
                "Gemini API Key (optional, for AI insights)")
        if not config.get("FINNHUB_API_KEY"):
            status["missing_config"].append(
                "Finnhub API Key (optional, for better data)")

        return jsonify(status)

    except Exception as e:
        logger.error(
            f"Failed to get news intelligence status: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# ============================================
# AI MARKET INTELLIGENCE ENDPOINTS (New Enhanced Version)
# ============================================


@api_bp.route("/market-intelligence/trigger", methods=["POST"])
def trigger_market_intelligence():
    """
    Manual trigger for AI-powered market intelligence analysis.
    Scans broad financial/geopolitical news and generates personalized recommendations.
    """
    if not hasattr(g, 'user') or not g.user:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        from utils import database as db
        from flask_app.services.market_intelligence_service import MarketIntelligenceService

        user_id = g.user.id
        user_email = g.user.email

        # Get user's API keys
        config = db.get_user_api_keys(user_id, decrypt=True)
        if not config.get("GMAIL_ADDRESS") or not config.get("GMAIL_APP_PASSWORD"):
            return jsonify({
                "error": "Gmail credentials not configured. Please add them in Settings."
            }), 400

        if not config.get("GEMINI_API_KEY"):
            return jsonify({
                "error": "Gemini API Key required for AI-powered recommendations. Please add it in Settings."
            }), 400

        # Add Gmail credentials to config
        config['gmail_address'] = config.get("GMAIL_ADDRESS")
        config['gmail_app_password'] = config.get("GMAIL_APP_PASSWORD")

        # Get user's shadow portfolio holdings
        holdings = db.get_shadow_positions(user_id, is_active=True)
        holding_tickers = [pos.get('ticker')
                           for pos in holdings if pos.get('ticker')]

        # Get user's risk profile, trading style, and available cash
        sim_settings = db.get_simulation_settings(user_id)
        risk_profile = sim_settings.get(
            'risk_profile', 'moderate') if sim_settings else 'moderate'
        available_cash = sim_settings.get(
            'current_cash', 0) if sim_settings else 0
        trading_style = sim_settings.get(
            'trading_style', 'swing_trading') if sim_settings else 'swing_trading'

        logger.info(f"Manual AI market intelligence trigger for {user_email}")
        logger.info(
            f"  Holdings: {len(holding_tickers)}, Risk: {risk_profile}, Style: {trading_style}, Cash: ${available_cash:,.2f}")

        # Initialize market intelligence service
        intelligence_service = MarketIntelligenceService(config)

        # Get hours_back from request (default 2 hours for manual trigger)
        hours_back = request.json.get('hours_back', 2) if request.json else 2

        # Generate intelligence and recommendations
        sent = intelligence_service.generate_market_intelligence(
            user_id=user_id,
            user_email=user_email,
            user_holdings=holding_tickers,
            risk_profile=risk_profile,
            available_cash=available_cash,
            hours_back=hours_back,
            trading_style=trading_style
        )

        if sent:
            return jsonify({
                "success": True,
                "message": f"AI market intelligence email sent to {user_email}",
                "holdings_count": len(holding_tickers),
                "risk_profile": risk_profile,
                "available_cash": available_cash,
                "hours_scanned": hours_back
            })
        else:
            return jsonify({
                "success": False,
                "message": "No significant market developments in the last {} hour(s)".format(hours_back),
                "holdings_count": len(holding_tickers),
                "risk_profile": risk_profile,
                "hours_scanned": hours_back
            })

    except Exception as e:
        logger.error(
            f"Manual market intelligence trigger failed: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/market-intelligence/status")
def get_market_intelligence_status():
    """
    Get status of AI market intelligence configuration and diagnostics.
    """
    if not hasattr(g, 'user') or not g.user:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        from utils import database as db

        user_id = g.user.id

        # Check configuration
        config = db.get_user_api_keys(user_id, decrypt=True)
        prefs = db.get_notification_preferences(user_id)

        # Get holdings and portfolio info
        holdings = db.get_shadow_positions(user_id, is_active=True)
        holding_tickers = [pos.get('ticker')
                           for pos in holdings if pos.get('ticker')]

        sim_settings = db.get_simulation_settings(user_id)
        risk_profile = sim_settings.get(
            'risk_profile', 'moderate') if sim_settings else 'moderate'
        available_cash = sim_settings.get(
            'current_cash', 0) if sim_settings else 0

        status = {
            "configured": bool(
                config.get("GMAIL_ADDRESS") and
                config.get("GMAIL_APP_PASSWORD") and
                config.get("GEMINI_API_KEY")
            ),
            "news_alerts_enabled": prefs.get("news_alerts", True),
            "notifications_enabled": config.get("notifications_enabled", True),
            "holdings_count": len(holding_tickers),
            "risk_profile": risk_profile,
            "available_cash": available_cash,
            "gmail_configured": bool(config.get("GMAIL_ADDRESS") and config.get("GMAIL_APP_PASSWORD")),
            "gemini_configured": bool(config.get("GEMINI_API_KEY")),
            "finnhub_configured": bool(config.get("FINNHUB_API_KEY")),
            "scan_schedule": "Every hour (top of the hour)",
            "features": {
                "broad_news_scanning": True,
                "geopolitical_analysis": True,
                "ai_recommendations": config.get("GEMINI_API_KEY") is not None,
                "personalized_risk_profile": True,
                "holdings_impact_analysis": True,
                "buy_sell_hold_suggestions": config.get("GEMINI_API_KEY") is not None
            },
            "missing_config": []
        }

        # Add missing configuration items
        if not config.get("GMAIL_ADDRESS") or not config.get("GMAIL_APP_PASSWORD"):
            status["missing_config"].append(
                "Gmail credentials (REQUIRED for email alerts)")
        if not config.get("GEMINI_API_KEY"):
            status["missing_config"].append(
                "Gemini API Key (REQUIRED for AI recommendations)")
        if not config.get("FINNHUB_API_KEY"):
            status["missing_config"].append(
                "Finnhub API Key (optional, improves data quality)")

        return jsonify(status)

    except Exception as e:
        logger.error(
            f"Failed to get market intelligence status: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/market-intelligence/debug", methods=["POST"])
def debug_market_intelligence():
    """
    Debug endpoint to see what the AI is analyzing without sending email.
    Returns the raw market analysis and recommendations.
    """
    if not hasattr(g, 'user') or not g.user:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        from utils import database as db
        from flask_app.services.market_intelligence_service import MarketIntelligenceService

        user_id = g.user.id
        config = db.get_user_api_keys(user_id, decrypt=True)

        if not config.get("GEMINI_API_KEY"):
            return jsonify({
                "error": "Gemini API Key required. Please add it in Settings."
            }), 400

        config['gmail_address'] = config.get("GMAIL_ADDRESS", "")
        config['gmail_app_password'] = config.get("GMAIL_APP_PASSWORD", "")

        # Get holdings and settings
        holdings = db.get_shadow_positions(user_id, is_active=True)
        holding_tickers = [pos.get('ticker')
                           for pos in holdings if pos.get('ticker')]

        sim_settings = db.get_simulation_settings(user_id)
        risk_profile = sim_settings.get(
            'risk_profile', 'moderate') if sim_settings else 'moderate'
        available_cash = sim_settings.get(
            'current_cash', 0) if sim_settings else 0
        trading_style = sim_settings.get(
            'trading_style', 'swing_trading') if sim_settings else 'swing_trading'

        logger.info(f"Debug: Analyzing market for {g.user.email}")

        # Initialize service
        intelligence_service = MarketIntelligenceService(config)

        # Get comprehensive market analysis
        market_analysis = intelligence_service._get_comprehensive_market_analysis()

        if not market_analysis:
            return jsonify({
                "error": "Failed to get market analysis from Gemini",
                "details": "Check logs for Gemini API errors"
            }), 500

        # Generate recommendations (if market analysis succeeded)
        recommendations = []
        if market_analysis.get('has_important_news'):
            recommendations = intelligence_service._generate_personalized_recommendations(
                market_analysis=market_analysis,
                user_holdings=holding_tickers,
                risk_profile=risk_profile,
                available_cash=available_cash,
                trading_style=trading_style
            )

        # Get holdings impact
        holdings_impact = []
        if holding_tickers and market_analysis.get('has_important_news'):
            holdings_impact = intelligence_service._analyze_holdings_impact(
                user_holdings=holding_tickers,
                market_analysis=market_analysis
            )

        return jsonify({
            "success": True,
            "market_analysis": market_analysis,
            "recommendations": recommendations,
            "holdings_impact": holdings_impact,
            "user_context": {
                "holdings": holding_tickers,
                "risk_profile": risk_profile,
                "trading_style": trading_style,
                "available_cash": available_cash
            }
        })

    except Exception as e:
        logger.error(f"Debug endpoint failed: {e}", exc_info=True)
        return jsonify({"error": str(e), "traceback": str(e)}), 500


@api_bp.route("/market-intelligence/force-send", methods=["POST"])
def force_send_market_intelligence():
    """
    Force send an email regardless of whether there's important news.
    Useful for testing email formatting and delivery.
    """
    if not hasattr(g, 'user') or not g.user:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        from utils import database as db
        from flask_app.services.market_intelligence_service import MarketIntelligenceService

        user_id = g.user.id
        user_email = g.user.email

        # Get user's API keys
        config = db.get_user_api_keys(user_id, decrypt=True)
        if not config.get("GMAIL_ADDRESS") or not config.get("GMAIL_APP_PASSWORD"):
            return jsonify({
                "error": "Gmail credentials not configured. Please add them in Settings."
            }), 400

        if not config.get("GEMINI_API_KEY"):
            return jsonify({
                "error": "Gemini API Key required. Please add it in Settings."
            }), 400

        config['gmail_address'] = config.get("GMAIL_ADDRESS")
        config['gmail_app_password'] = config.get("GMAIL_APP_PASSWORD")

        # Get holdings and settings
        holdings = db.get_shadow_positions(user_id, is_active=True)
        holding_tickers = [pos.get('ticker')
                           for pos in holdings if pos.get('ticker')]

        sim_settings = db.get_simulation_settings(user_id)
        risk_profile = sim_settings.get(
            'risk_profile', 'moderate') if sim_settings else 'moderate'
        available_cash = sim_settings.get(
            'current_cash', 0) if sim_settings else 0
        trading_style = sim_settings.get(
            'trading_style', 'swing_trading') if sim_settings else 'swing_trading'

        logger.info(f"Force send: Generating intelligence for {user_email}")

        # Initialize service
        intelligence_service = MarketIntelligenceService(config)

        # Get market analysis
        market_analysis = intelligence_service._get_comprehensive_market_analysis()

        if not market_analysis:
            return jsonify({
                "error": "Failed to get market analysis from Gemini"
            }), 500

        # Force has_important_news to True for testing
        market_analysis['has_important_news'] = True

        # Generate recommendations
        recommendations = intelligence_service._generate_personalized_recommendations(
            market_analysis=market_analysis,
            user_holdings=holding_tickers,
            risk_profile=risk_profile,
            available_cash=available_cash,
            trading_style=trading_style
        )

        # Get holdings impact
        holdings_impact = intelligence_service._analyze_holdings_impact(
            user_holdings=holding_tickers,
            market_analysis=market_analysis
        )

        # Force send email
        sent = intelligence_service._send_intelligence_email(
            user_email=user_email,
            market_analysis=market_analysis,
            recommendations=recommendations,
            holdings_impact=holdings_impact,
            risk_profile=risk_profile
        )

        if sent:
            return jsonify({
                "success": True,
                "message": f"Test email forcefully sent to {user_email}",
                "market_sentiment": market_analysis.get('market_sentiment'),
                "recommendations_count": len(recommendations),
                "holdings_impact_count": len(holdings_impact)
            })
        else:
            return jsonify({
                "success": False,
                "error": "Email sending failed (check Gmail credentials)"
            }), 500

    except Exception as e:
        logger.error(f"Force send failed: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/debug/user-keys")
def debug_user_keys():
    """
    Debug endpoint to see what API keys are actually stored and loaded.
    """
    if not hasattr(g, 'user') or not g.user:
        return jsonify({"error": "Not logged in"}), 401

    try:
        from utils import database as db

        # Get keys from g.user (what's currently loaded in memory)
        loaded_keys = g.user.get_api_keys() if hasattr(g.user, 'get_api_keys') else {}

        # Get keys directly from database
        db_keys = db.get_user_api_keys(g.user.id, decrypt=True) or {}

        return jsonify({
            "user_id": g.user.id,
            "user_email": g.user.email,
            "loaded_in_memory": {
                "finnhub": bool(loaded_keys.get('FINNHUB_API_KEY')),
                "alpaca": bool(loaded_keys.get('ALPACA_API_KEY')),
                "gemini": bool(loaded_keys.get('GEMINI_API_KEY')),
                "finnhub_preview": loaded_keys.get('FINNHUB_API_KEY', '')[:10] + '...' if loaded_keys.get('FINNHUB_API_KEY') else 'NOT_SET'
            },
            "in_database": {
                "finnhub": bool(db_keys.get('FINNHUB_API_KEY')),
                "alpaca": bool(db_keys.get('ALPACA_API_KEY')),
                "gemini": bool(db_keys.get('GEMINI_API_KEY')),
                "finnhub_preview": db_keys.get('FINNHUB_API_KEY', '')[:10] + '...' if db_keys.get('FINNHUB_API_KEY') else 'NOT_SET'
            },
            "diagnosis": "Keys are " + ("LOADED CORRECTLY" if loaded_keys.get('FINNHUB_API_KEY') and db_keys.get('FINNHUB_API_KEY') else "MISSING OR NOT LOADED")
        })

    except Exception as e:
        logger.error(f"Debug keys failed: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

# ========================================
# NEW FEATURE ENDPOINTS
# ========================================


@api_bp.route("/macro-data")
def get_macro_data():
    """Get global macro indicators (SPY, VIX, 10Y, DXY, BTC, Gold, Oil)."""
    try:
        config = get_config()
        stock_service = StockService(config)

        # Fetch key macro indicators
        macro_tickers = {
            'SPY': 'spy',
            'VIX': 'vix',
            '^TNX': 'yield10y',  # 10-Year Treasury Yield
            'DX-Y.NYB': 'dxy',  # Dollar Index
            'BTC-USD': 'btc',
            'GC=F': 'gold',
            'CL=F': 'oil'
        }

        results = {}
        for ticker, key in macro_tickers.items():
            try:
                quote = stock_service.get_realtime_quote(ticker)
                if quote:
                    price = quote.get('current', 0)
                    prev_close = quote.get('previous_close', price)
                    change_pct = ((price - prev_close) /
                                  prev_close * 100) if prev_close else 0

                    if key == 'vix':
                        results[key] = {
                            'value': f"{price:.1f}",
                            'label': 'High Fear' if price > 25 else 'Moderate' if price > 15 else 'Low Fear'
                        }
                    elif key == 'yield10y':
                        results[key] = {
                            'value': f"{price:.2f}",
                            # In basis points
                            'change': round(change_pct * 100, 0)
                        }
                    else:
                        results[key] = {
                            'price': f"{price:,.0f}" if price > 100 else f"{price:.2f}",
                            'change': round(change_pct, 2)
                        }
            except Exception as e:
                logger.warning(f"Failed to fetch {ticker}: {e}")

        return jsonify(results)

    except Exception as e:
        logger.error(f"Macro data fetch failed: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/earnings-calendar")
def get_earnings_calendar():
    """Get upcoming earnings for user's holdings."""
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Not logged in"}), 401

        config = get_config()
        stock_service = StockService(config)
        trading_service = TradingService(config)

        # Get user's Alpaca positions
        positions = trading_service.get_positions()

        earnings_data = []
        for position in positions:
            ticker = position.get('ticker')
            if not ticker:
                continue

            try:
                # Get earnings calendar from Finnhub
                earnings = stock_service.get_earnings_calendar(ticker)
                if earnings:
                    earnings_data.append({
                        'ticker': ticker,
                        'earnings_date': earnings.get('date'),
                        'eps_estimate': earnings.get('epsEstimate'),
                        'eps_actual': earnings.get('epsActual'),
                        'quarter': earnings.get('quarter'),
                        'year': earnings.get('year')
                    })
            except:
                pass

        return jsonify(earnings_data)

    except Exception as e:
        logger.error(f"Earnings calendar failed: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/insider-trades/<ticker>")
def get_insider_trades(ticker):
    """Get recent insider trades for a ticker."""
    try:
        config = get_config()

        finnhub_key = config.get('FINNHUB_API_KEY', '')
        logger.info(
            f"Insider trades request for {ticker}. API key present: {bool(finnhub_key)}")

        # Check if Finnhub API key is available
        if not finnhub_key:
            return jsonify({"error": "Finnhub API key required. Please add your Finnhub API key in Settings page (not .env file)."}), 400

        stock_service = StockService(config)

        # Fetch insider transactions from Finnhub
        try:
            insiders = stock_service.get_insider_trades(ticker)
            if insiders is None:
                return jsonify({"error": "No insider data available for this ticker"}), 404
            return jsonify(insiders if insiders else [])
        except Exception as method_error:
            logger.error(f"Failed to fetch insider trades: {method_error}")
            return jsonify({"error": f"Failed to fetch insider trades: {str(method_error)}"}), 500

    except Exception as e:
        logger.error(f"Insider trades fetch failed: {e}")
        return jsonify({"error": f"Failed to fetch insider trades: {str(e)}"}), 500


@api_bp.route("/sector-rotation")
def get_sector_rotation():
    """Get sector performance heatmap data."""
    try:
        import yfinance as yf

        config = get_config()
        stock_service = StockService(config)

        # Sector ETFs to track
        sectors = {
            'XLK': 'Technology',
            'XLF': 'Financials',
            'XLE': 'Energy',
            'XLV': 'Healthcare',
            'XLI': 'Industrials',
            'XLY': 'Consumer Disc',
            'XLP': 'Consumer Staples',
            'XLU': 'Utilities',
            'XLRE': 'Real Estate',
            'XLB': 'Materials',
            'XLC': 'Communications'
        }

        sector_data = []
        for etf, sector_name in sectors.items():
            try:
                # Try Finnhub first
                quote = stock_service.get_realtime_quote(etf)

                if quote and quote.get('current') and quote.get('previous_close'):
                    price = quote.get('current', 0)
                    prev_close = quote.get('previous_close', price)
                    change_pct = ((price - prev_close) /
                                  prev_close * 100) if prev_close else 0

                    sector_data.append({
                        'sector': sector_name,
                        'etf': etf,
                        'change': round(change_pct, 2),
                        'price': round(price, 2)
                    })
                    logger.info(
                        f"Finnhub: {etf} ${price:.2f} ({change_pct:+.2f}%)")
                else:
                    # Fallback to yfinance if Finnhub fails
                    logger.info(
                        f"Finnhub failed for {etf}, trying yfinance fallback")
                    ticker_obj = yf.Ticker(etf)
                    info = ticker_obj.info

                    current_price = info.get(
                        'regularMarketPrice') or info.get('currentPrice', 0)
                    prev_close = info.get('previousClose', current_price)

                    if current_price and prev_close:
                        change_pct = (
                            (current_price - prev_close) / prev_close * 100)
                        sector_data.append({
                            'sector': sector_name,
                            'etf': etf,
                            'change': round(change_pct, 2),
                            'price': round(current_price, 2)
                        })
                        logger.info(
                            f"yfinance: {etf} ${current_price:.2f} ({change_pct:+.2f}%)")
            except Exception as sector_error:
                logger.warning(
                    f"Failed to fetch {etf} from Finnhub: {sector_error}")
                # Last resort: try yfinance even if exception occurred
                try:
                    ticker_obj = yf.Ticker(etf)
                    info = ticker_obj.info
                    current_price = info.get(
                        'regularMarketPrice') or info.get('currentPrice', 0)
                    prev_close = info.get('previousClose', current_price)

                    if current_price and prev_close:
                        change_pct = (
                            (current_price - prev_close) / prev_close * 100)
                        sector_data.append({
                            'sector': sector_name,
                            'etf': etf,
                            'change': round(change_pct, 2),
                            'price': round(current_price, 2)
                        })
                        logger.info(
                            f"yfinance (backup): {etf} ${current_price:.2f} ({change_pct:+.2f}%)")
                except Exception as yf_error:
                    logger.error(
                        f"Both Finnhub and yfinance failed for {etf}: {yf_error}")

        # If no data was fetched, return error
        if not sector_data:
            logger.warning("No sector data available from any source")
            return jsonify({"error": "Unable to fetch sector data. Please check your Finnhub API key or try again later."}), 503

        # Sort by performance
        sector_data.sort(key=lambda x: x['change'], reverse=True)

        return jsonify(sector_data)

    except Exception as e:
        logger.error(f"Sector rotation fetch failed: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/portfolio-correlation")
def get_portfolio_correlation():
    """Calculate correlation matrix for user's portfolio."""
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Not logged in"}), 401

        import pandas as pd
        import yfinance as yf
        from datetime import timedelta

        config = get_config()
        trading_service = TradingService(config)

        # Get user's Alpaca positions
        positions = trading_service.get_positions()
        tickers = [p.get('ticker') for p in positions if p.get('ticker')]

        if len(tickers) < 2:
            return jsonify({"error": "Need at least 2 holdings to calculate correlation"}), 400

        # Fetch price history for all tickers
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)  # 90 days of history

        # Download all tickers at once for aligned dates
        try:
            df = yf.download(tickers[:10], start=start_date,
                             end=end_date, progress=False)['Close']

            # Handle single ticker case (returns Series not DataFrame)
            if len(tickers) == 1:
                return jsonify({"error": "Need at least 2 holdings to calculate correlation"}), 400

            # Drop any columns with all NaN values
            if isinstance(df, pd.DataFrame):
                df = df.dropna(axis=1, how='all')

            if df.empty or (isinstance(df, pd.DataFrame) and len(df.columns) < 2):
                return jsonify({"error": "Not enough price data"}), 400

        except Exception as download_error:
            logger.error(f"Failed to download price data: {download_error}")
            return jsonify({"error": "Failed to fetch price data"}), 500

        # Calculate correlation matrix
        try:
            correlation_matrix = df.corr()
        except Exception as corr_error:
            logger.error(f"Correlation calculation failed: {corr_error}")
            return jsonify({"error": "Failed to calculate correlation"}), 500

        # Convert to JSON format
        result = {
            'tickers': list(correlation_matrix.columns),
            'matrix': correlation_matrix.values.tolist()
        }

        return jsonify(result)

    except Exception as e:
        logger.error(f"Portfolio correlation failed: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================
# SWING TRADING ADVANCED FEATURES
# ============================================

@api_bp.route("/backtest", methods=["POST"])
def run_backtest():
    """Run backtesting simulation. Default hold period aligns with user's trading style."""
    try:
        data = request.get_json()
        ticker = data.get("ticker", "").upper()
        strategy = data.get("strategy", "rsi")
        period = data.get("period", "1y")

        # Default hold_days matches the user's trading style; explicit value overrides
        DEFAULT_HOLD = {"day_trading": 1, "swing_trading": 5, "long_term": 30}
        style_default = DEFAULT_HOLD.get(get_trading_style(), 5)
        hold_days = data.get("hold_days", style_default)

        if not ticker:
            return jsonify({"error": "Ticker required"}), 400

        import yfinance as yf
        import pandas as pd
        import numpy as np
        from datetime import timedelta

        # Download historical data
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)

        if hist.empty:
            return jsonify({"error": "No data available for ticker"}), 400

        # Calculate indicators
        hist['RSI'] = calculate_rsi(hist['Close'])
        hist['SMA_20'] = hist['Close'].rolling(window=20).mean()
        hist['SMA_50'] = hist['Close'].rolling(window=50).mean()
        hist['High_20'] = hist['High'].rolling(window=20).max()

        # Run strategy simulation
        trades = []
        equity_curve = [
            {'date': hist.index[0].strftime('%Y-%m-%d'), 'value': 10000}]
        current_cash = 10000
        position = None

        for i in range(50, len(hist)):
            date = hist.index[i]
            price = hist['Close'].iloc[i]
            rsi = hist['RSI'].iloc[i]

            # Entry logic based on strategy
            if position is None:
                entry_signal = False

                if strategy == 'rsi' and rsi < 30:
                    entry_signal = True
                elif strategy == 'ma_crossover' and hist['SMA_20'].iloc[i] > hist['SMA_50'].iloc[i] and hist['SMA_20'].iloc[i-1] <= hist['SMA_50'].iloc[i-1]:
                    entry_signal = True
                elif strategy == 'breakout' and price > hist['High_20'].iloc[i-1]:
                    entry_signal = True

                if entry_signal:
                    shares = current_cash / price
                    position = {
                        'entry_date': date,
                        'entry_price': price,
                        'shares': shares,
                        'hold_days': 0
                    }
                    current_cash = 0

            # Exit logic
            elif position is not None:
                position['hold_days'] += 1
                exit_signal = False

                if strategy == 'rsi' and rsi > 70:
                    exit_signal = True
                elif position['hold_days'] >= hold_days:
                    exit_signal = True

                if exit_signal:
                    exit_price = price
                    pnl = (exit_price -
                           position['entry_price']) * position['shares']
                    pnl_percent = (
                        (exit_price - position['entry_price']) / position['entry_price']) * 100

                    trades.append({
                        'id': len(trades),
                        'entryDate': position['entry_date'].strftime('%Y-%m-%d'),
                        'exitDate': date.strftime('%Y-%m-%d'),
                        'entryPrice': round(position['entry_price'], 2),
                        'exitPrice': round(exit_price, 2),
                        'pnlPercent': round(pnl_percent, 2),
                        'holdDays': position['hold_days']
                    })

                    current_cash = position['shares'] * exit_price
                    position = None

            # Update equity curve
            portfolio_value = current_cash if position is None else position['shares'] * price
            equity_curve.append({'date': date.strftime(
                '%Y-%m-%d'), 'value': round(portfolio_value, 2)})

        # Calculate metrics
        winning_trades = [t for t in trades if t['pnlPercent'] > 0]
        win_rate = (len(winning_trades) / len(trades) * 100) if trades else 0
        total_return = ((equity_curve[-1]['value'] - 10000) / 10000) * 100

        # Max drawdown
        peak = equity_curve[0]['value']
        max_dd = 0
        for point in equity_curve:
            if point['value'] > peak:
                peak = point['value']
            dd = ((peak - point['value']) / peak) * 100
            max_dd = max(max_dd, dd)

        # Profit factor
        gross_profit = sum([t['pnlPercent']
                           for t in trades if t['pnlPercent'] > 0])
        gross_loss = abs(sum([t['pnlPercent']
                         for t in trades if t['pnlPercent'] < 0]))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0

        # Sharpe ratio (simplified)
        returns = [trades[i]['pnlPercent'] / 100 for i in range(len(trades))]
        if returns:
            avg_return = np.mean(returns)
            std_return = np.std(returns)
            sharpe = (avg_return / std_return *
                      np.sqrt(252/hold_days)) if std_return > 0 else 0
        else:
            sharpe = 0

        avg_hold = np.mean([t['holdDays'] for t in trades]) if trades else 0

        result = {
            'totalReturn': round(total_return, 2),
            'winRate': round(win_rate, 2),
            'totalTrades': len(trades),
            'maxDrawdown': round(max_dd, 2),
            'profitFactor': round(profit_factor, 2),
            'sharpeRatio': round(sharpe, 2),
            'avgHoldDays': round(avg_hold, 1),
            'equityCurve': equity_curve[-100:],  # Last 100 points
            'trades': trades[-20:]  # Last 20 trades
        }

        return jsonify(result)

    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/multi-timeframe")
def get_multi_timeframe():
    """Multi-timeframe analysis for swing trading."""
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Not logged in"}), 401

        from utils import database as db
        import yfinance as yf

        # Get first holding as example ticker (or allow passing ticker param)
        ticker = request.args.get('ticker')
        if not ticker:
            holdings = db.get_shadow_positions(user_id, is_active=True)
            if not holdings:
                return jsonify({"error": "No holdings found"}), 400
            ticker = holdings[0].get('ticker')

        stock = yf.Ticker(ticker)

        # Weekly data
        weekly = stock.history(period='6mo', interval='1wk')
        weekly_sma20 = weekly['Close'].rolling(20).mean().iloc[-1]
        weekly_sma50 = weekly['Close'].rolling(50).mean().iloc[-1]
        weekly_rsi = calculate_rsi(weekly['Close']).iloc[-1]
        weekly_trend = 'bullish' if weekly['Close'].iloc[-1] > weekly_sma20 else 'bearish'

        # Daily data
        daily = stock.history(period='3mo', interval='1d')
        daily_support = daily['Low'].rolling(20).min().iloc[-1]
        daily_resistance = daily['High'].rolling(20).max().iloc[-1]
        macd = calculate_macd(daily['Close'])
        daily_trend = 'bullish' if daily['Close'].iloc[-1] > daily['Close'].rolling(
            20).mean().iloc[-1] else 'bearish'

        # 4-hour data (approximated from hourly)
        hourly = stock.history(period='1mo', interval='1h')
        four_hour = hourly.resample('4h').agg(
            {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()
        momentum = ((four_hour['Close'].iloc[-1] -
                    four_hour['Close'].iloc[-5]) / four_hour['Close'].iloc[-5]) * 100
        four_hour_trend = 'bullish' if momentum > 0 else 'bearish'
        stoch_rsi = (weekly_rsi - 30) / (70 - 30) * 100  # Simplified

        # Helper function to safely round and handle NaN
        def safe_round(value, decimals=2):
            if value is None or (isinstance(value, float) and np.isnan(value)):
                return 0
            return round(float(value), decimals)

        trading_style = get_trading_style()
        STYLE_LABELS = {
            "day_trading":   "Day Trading",
            "swing_trading": "Swing Trading",
            "long_term":     "Long-Term Investing",
        }

        result = {
            'trading_style': trading_style,
            'trading_style_label': STYLE_LABELS.get(trading_style, "Swing Trading"),
            'weekly': {
                'trend': weekly_trend,
                'sma20': safe_round(weekly_sma20, 2),
                'sma50': safe_round(weekly_sma50, 2),
                'rsi': safe_round(weekly_rsi, 1),
                'signal': 'Buy on pullbacks' if weekly_trend == 'bullish' else 'Short rallies'
            },
            'daily': {
                'trend': daily_trend,
                'support': safe_round(daily_support, 2),
                'resistance': safe_round(daily_resistance, 2),
                'macd': safe_round(macd, 2),
                'entryZone': f"${safe_round(daily_support, 2):.2f} - ${safe_round(daily_support * 1.02, 2):.2f}" if daily_trend == 'bullish' else f"${safe_round(daily_resistance * 0.98, 2):.2f} - ${safe_round(daily_resistance, 2):.2f}"
            },
            'fourHour': {
                'trend': four_hour_trend,
                'momentum': safe_round(momentum, 2),
                'volume': 'Above average' if four_hour['Volume'].iloc[-1] > four_hour['Volume'].mean() else 'Below average',
                'stochRsi': safe_round(stoch_rsi, 0),
                'timing': 'Enter now' if abs(momentum) < 2 else 'Wait for consolidation'
            }
        }

        return jsonify(result)

    except Exception as e:
        logger.error(f"Multi-timeframe analysis failed: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/volatility-surface")
def get_volatility_surface():
    """Volatility surface analysis for swing trading."""
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Not logged in"}), 401

        from utils import database as db
        import yfinance as yf
        import numpy as np

        # Get ticker
        ticker = request.args.get('ticker')
        if not ticker:
            holdings = db.get_shadow_positions(user_id, is_active=True)
            if not holdings:
                return jsonify({"error": "No holdings found"}), 400
            ticker = holdings[0].get('ticker')

        stock = yf.Ticker(ticker)
        hist = stock.history(period='1y')

        # Calculate historical volatility
        returns = hist['Close'].pct_change().dropna()
        hist_vol_30 = returns.tail(30).std() * np.sqrt(252) * 100
        hist_vol_90 = returns.tail(90).std() * np.sqrt(252) * 100

        # Implied volatility (mock - would need options data)
        implied_vol = hist_vol_30 * 1.15  # Typically slightly higher

        # Volatility percentile
        rolling_vol = returns.rolling(30).std() * np.sqrt(252) * 100
        vol_percentile = (rolling_vol < hist_vol_30).sum() / \
            len(rolling_vol) * 100

        # Determine regime
        if hist_vol_30 > hist_vol_90 * 1.3:
            regime = 'high'
        elif hist_vol_30 < hist_vol_90 * 0.7:
            regime = 'low'
        else:
            regime = 'normal'

        # Expected moves (1 std dev)
        current_price = hist['Close'].iloc[-1]
        expected_daily_move = current_price * \
            (hist_vol_30 / 100) / np.sqrt(252)
        expected_weekly_move = expected_daily_move * np.sqrt(5)

        # Position sizing recommendations
        if regime == 'high':
            position_sizing = 'Reduce to 50-70% normal size'
            stop_loss_strategy = 'Use 1.5x ATR stops'
            optimal_entry = 'After vol spike subsides'
            stop_width = 8.0
        elif regime == 'low':
            position_sizing = 'Normal size'
            stop_loss_strategy = 'Use 1x ATR stops'
            optimal_entry = 'Standard pullback entries'
            stop_width = 3.0
        else:
            position_sizing = 'Normal size'
            stop_loss_strategy = 'Use 1.2x ATR stops'
            optimal_entry = 'Follow typical patterns'
            stop_width = 5.0

        # Term structure (mock data)
        term_structure = [
            {'days': 7, 'iv': hist_vol_30 * 0.95},
            {'days': 14, 'iv': hist_vol_30 * 1.0},
            {'days': 30, 'iv': hist_vol_30 * 1.05},
            {'days': 60, 'iv': hist_vol_30 * 1.10},
            {'days': 90, 'iv': hist_vol_90}
        ]

        # Vol smile (mock data)
        vol_smile = [
            {'strike': current_price * 0.90, 'iv': implied_vol * 1.15},
            {'strike': current_price * 0.95, 'iv': implied_vol * 1.08},
            {'strike': current_price * 1.00, 'iv': implied_vol},
            {'strike': current_price * 1.05, 'iv': implied_vol * 1.05},
            {'strike': current_price * 1.10, 'iv': implied_vol * 1.10}
        ]

        result = {
            'historicalVol30': round(hist_vol_30, 1),
            'historicalVol90': round(hist_vol_90, 1),
            'impliedVol': round(implied_vol, 1),
            'volPercentile': round(vol_percentile, 0),
            'regime': regime,
            'expectedDailyMove': round(expected_daily_move, 2),
            'expectedDailyMovePercent': round((expected_daily_move / current_price) * 100, 1),
            'expectedWeeklyMove': round(expected_weekly_move, 2),
            'expectedWeeklyMovePercent': round((expected_weekly_move / current_price) * 100, 1),
            'optimalEntry': optimal_entry,
            'stopLossWidth': stop_width,
            'positionSizing': position_sizing,
            'stopLossStrategy': stop_loss_strategy,
            'termStructure': term_structure,
            'volSmile': vol_smile
        }

        return jsonify(result)

    except Exception as e:
        logger.error(f"Volatility surface failed: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/portfolio-rebalance")
def get_portfolio_rebalance():
    """AI-powered portfolio rebalancing analysis."""
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Not logged in"}), 401

        config = get_config()
        trading_service = TradingService(config)

        # Get user's Alpaca positions
        positions = trading_service.get_positions()
        if not positions:
            return jsonify({"error": "No holdings to rebalance"}), 400

        # Transform Alpaca positions to match expected format
        holdings = []
        for pos in positions:
            holdings.append({
                'ticker': pos.get('ticker'),
                'shares': pos.get('shares', 0),
                'current_value': pos.get('market_value', 0)
            })

        total_value = sum([h.get('current_value', 0) for h in holdings])

        # Handle zero total value
        if total_value == 0:
            logger.warning(
                "Portfolio total value is zero - cannot calculate rebalancing")
            return jsonify({"error": "Portfolio has no value. Add positions first."}), 400

        # Trading-style-aware drift thresholds
        trading_style = get_trading_style()
        DRIFT_THRESHOLDS = {
            "day_trading":   {"min": 3, "moderate": 8,  "high": 12},
            "swing_trading": {"min": 5, "moderate": 10, "high": 15},
            "long_term":     {"min": 8, "moderate": 15, "high": 25},
        }
        thresholds = DRIFT_THRESHOLDS.get(trading_style, DRIFT_THRESHOLDS["swing_trading"])
        min_drift = thresholds["min"]
        moderate_thresh = thresholds["moderate"]
        high_thresh = thresholds["high"]

        # Calculate current allocations
        analyzed_holdings = []
        for h in holdings:
            ticker = h.get('ticker')
            value = h.get('current_value', 0)
            current_percent = (value / total_value) * \
                100 if total_value > 0 else 0

            # Target is equal weight for simplicity (or could be from user preferences)
            target_percent = 100 / len(holdings)
            drift = current_percent - target_percent

            # Determine action — threshold scales with trading style
            if abs(drift) < min_drift:
                action = None
            elif drift > 0:
                action = f"SELL {ticker} ${abs(drift * total_value / 100):.0f}"
            else:
                action = f"BUY {ticker} ${abs(drift * total_value / 100):.0f}"

            analyzed_holdings.append({
                'ticker': ticker,
                'value': value,
                'currentPercent': round(current_percent, 1),
                'targetPercent': round(target_percent, 1),
                'drift': round(drift, 1),
                'action': action
            })

        # AI Recommendations (thresholds vary by trading style)
        recommendations = []

        # High drift warning
        high_drift = [h for h in analyzed_holdings if abs(h['drift']) > high_thresh]
        if high_drift:
            recommendations.append({
                'priority': 'high',
                'title': 'Significant Drift Detected',
                'description': f"{len(high_drift)} position(s) drifted >{high_thresh}% from target. Rebalancing recommended to maintain diversification.",
                'trades': [h['action'] for h in high_drift if h['action']]
            })

        # Moderate drift
        moderate_drift = [
            h for h in analyzed_holdings if moderate_thresh < abs(h['drift']) <= high_thresh]
        if moderate_drift:
            recommendations.append({
                'priority': 'medium',
                'title': 'Moderate Drift',
                'description': f"{len(moderate_drift)} position(s) need adjustment. Consider rebalancing this month.",
                'trades': [h['action'] for h in moderate_drift if h['action']]
            })

        # Well balanced
        if len(high_drift) == 0 and len(moderate_drift) == 0:
            recommendations.append({
                'priority': 'low',
                'title': 'Portfolio Well-Balanced',
                'description': f'All positions within {min_drift}% of target. No action needed.',
                'trades': None
            })

        # Scenarios
        conservative_trades = len(
            [h for h in analyzed_holdings if abs(h['drift']) > moderate_thresh])
        aggressive_trades = len(
            [h for h in analyzed_holdings if abs(h['drift']) > high_thresh])

        result = {
            'holdings': analyzed_holdings,
            'recommendations': recommendations,
            'scenarios': {
                'conservative': {
                    'trades': conservative_trades,
                    'cost': conservative_trades * 1  # $1 per trade estimate
                },
                'aggressive': {
                    'trades': aggressive_trades,
                    'cost': aggressive_trades * 1
                }
            }
        }

        return jsonify(result)

    except Exception as e:
        logger.error(f"Portfolio rebalance failed: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/portfolio-rebalance/execute", methods=["POST"])
def execute_portfolio_rebalance():
    """Execute rebalancing trades via Alpaca."""
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Not logged in"}), 401

        data = request.get_json() or {}
        scenario = data.get("scenario", "conservative")
        threshold = 5 if scenario == "conservative" else 15

        config = get_config()
        trading_service = TradingService(config)

        if not trading_service.is_connected():
            return jsonify({"error": "Alpaca not connected. Add API keys in Settings."}), 400

        # Get current positions
        positions = trading_service.get_positions()
        if not positions:
            return jsonify({"error": "No positions to rebalance"}), 400

        total_value = sum(float(p.get('market_value', 0)) for p in positions)
        if total_value == 0:
            return jsonify({"error": "Portfolio has no value"}), 400

        target_value = total_value / len(positions)
        submitted = []
        errors = []

        for pos in positions:
            ticker = pos.get('ticker')
            current_value = float(pos.get('market_value', 0))
            shares = float(pos.get('shares', 0))
            if shares == 0:
                continue

            current_price = current_value / shares
            drift_pct = ((current_value - target_value) / total_value) * 100

            if abs(drift_pct) <= threshold:
                continue  # Within threshold, skip

            drift_value = current_value - target_value

            if drift_value > 0:
                # Overweight: sell excess
                sell_value = drift_value
                qty = round(sell_value / current_price, 2)
                if qty > 0 and qty <= shares:
                    result = trading_service.sell(ticker, qty)
                    if result.get('success'):
                        submitted.append(
                            f"SELL {qty} {ticker} (${sell_value:.0f})")
                    else:
                        errors.append(
                            f"{ticker}: {result.get('error', 'sell failed')}")
            else:
                # Underweight: buy more
                buy_value = abs(drift_value)
                qty = round(buy_value / current_price, 2)
                if qty > 0:
                    result = trading_service.buy(ticker, qty)
                    if result.get('success'):
                        submitted.append(
                            f"BUY {qty} {ticker} (${buy_value:.0f})")
                    else:
                        errors.append(
                            f"{ticker}: {result.get('error', 'buy failed')}")

        if not submitted and not errors:
            return jsonify({"message": "No trades needed - portfolio is balanced"}), 200

        return jsonify({
            "submitted": submitted,
            "errors": errors,
            "scenario": scenario
        })

    except Exception as e:
        logger.error(f"Portfolio rebalance execute failed: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/trigger-email-job", methods=["POST"])
def trigger_email_job():
    """Manually trigger any scheduled email job for testing."""
    if not hasattr(g, 'user') or not g.user:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    job = data.get("job", "").strip().lower()

    valid_jobs = {
        "preview": "market_preview_job",
        "intelligence": "market_intelligence_job",
        "close": "market_close_summary_job",
        "digest": "daily_digest_job",
    }

    if job not in valid_jobs:
        return jsonify({"error": f"Unknown job. Valid: {list(valid_jobs.keys())}"}), 400

    try:
        from flask_app.scheduler import (
            market_preview_job,
            market_intelligence_job,
            market_close_summary_job,
            daily_digest_job,
        )

        job_funcs = {
            "preview": market_preview_job,
            "intelligence": market_intelligence_job,
            "close": market_close_summary_job,
            "digest": daily_digest_job,
        }

        logger.info(
            f"Manually triggering {valid_jobs[job]} for user {g.user.id}")
        job_funcs[job]()

        return jsonify({"success": True, "message": f"Triggered {valid_jobs[job]}"})

    except Exception as e:
        logger.error(f"Manual trigger of {job} failed: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# Helper functions
def calculate_rsi(series, period=14):
    """Calculate RSI indicator."""
    import pandas as pd
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(series):
    """Calculate MACD indicator."""
    ema_12 = series.ewm(span=12, adjust=False).mean()
    ema_26 = series.ewm(span=26, adjust=False).mean()
    macd = ema_12 - ema_26
    return macd.iloc[-1] if len(macd) > 0 else 0
