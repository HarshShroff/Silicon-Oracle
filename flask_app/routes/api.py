"""
Silicon Oracle - API Routes
RESTful API endpoints for AJAX calls
"""

import logging
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
    """Get AI Deep Dive analysis."""
    from flask_app.services.gemini_service import GeminiService
    from utils.ticker_utils import normalize_ticker

    gemini_service = GeminiService(get_config())
    html, score, label = gemini_service.analyze_ticker(
        normalize_ticker(ticker))

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
    """Get AI interpretation of Oracle factors."""
    from flask_app.services.gemini_service import GeminiService
    from utils.ticker_utils import normalize_ticker

    ticker = normalize_ticker(ticker)

    # Get Oracle score first
    oracle_service = EnhancedOracleService(get_config())
    oracle_data = oracle_service.calculate_enhanced_oracle_score(ticker)

    # Get AI interpretation
    gemini_service = GeminiService(get_config())
    interpretation = gemini_service.get_factor_interpretation(ticker, oracle_data)

    if interpretation == "Gemini API Key Required":
        return jsonify({"locked": True, "interpretation": None})

    return jsonify({"locked": False, "interpretation": interpretation})


@api_bp.route("/oracle/pattern-analysis/<ticker>")
def get_oracle_pattern_analysis(ticker):
    """Get AI pattern analysis for a ticker."""
    from flask_app.services.gemini_service import GeminiService
    from utils.ticker_utils import normalize_ticker

    gemini_service = GeminiService(get_config())
    pattern_analysis = gemini_service.get_pattern_analysis(normalize_ticker(ticker))

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

    # Only update password if provided
    gmail_password = data.get("gmail_password", "").strip()
    if gmail_password:
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
        holding_tickers = [pos.get('ticker') for pos in holdings if pos.get('ticker')]

        logger.info(f"Manual news intelligence trigger for {user_email} with {len(holding_tickers)} holdings")

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
        logger.error(f"Manual news intelligence trigger failed: {e}", exc_info=True)
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
        holding_tickers = [pos.get('ticker') for pos in holdings if pos.get('ticker')]

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
            status["missing_config"].append("Gmail credentials (required for email alerts)")
        if not config.get("GEMINI_API_KEY"):
            status["missing_config"].append("Gemini API Key (optional, for AI insights)")
        if not config.get("FINNHUB_API_KEY"):
            status["missing_config"].append("Finnhub API Key (optional, for better data)")

        return jsonify(status)

    except Exception as e:
        logger.error(f"Failed to get news intelligence status: {e}", exc_info=True)
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
        holding_tickers = [pos.get('ticker') for pos in holdings if pos.get('ticker')]

        # Get user's risk profile and available cash
        sim_settings = db.get_simulation_settings(user_id)
        risk_profile = sim_settings.get('risk_profile', 'moderate') if sim_settings else 'moderate'
        available_cash = sim_settings.get('current_cash', 0) if sim_settings else 0

        logger.info(f"Manual AI market intelligence trigger for {user_email}")
        logger.info(f"  Holdings: {len(holding_tickers)}, Risk: {risk_profile}, Cash: ${available_cash:,.2f}")

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
            hours_back=hours_back
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
        logger.error(f"Manual market intelligence trigger failed: {e}", exc_info=True)
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
        holding_tickers = [pos.get('ticker') for pos in holdings if pos.get('ticker')]

        sim_settings = db.get_simulation_settings(user_id)
        risk_profile = sim_settings.get('risk_profile', 'moderate') if sim_settings else 'moderate'
        available_cash = sim_settings.get('current_cash', 0) if sim_settings else 0

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
            status["missing_config"].append("Gmail credentials (REQUIRED for email alerts)")
        if not config.get("GEMINI_API_KEY"):
            status["missing_config"].append("Gemini API Key (REQUIRED for AI recommendations)")
        if not config.get("FINNHUB_API_KEY"):
            status["missing_config"].append("Finnhub API Key (optional, improves data quality)")

        return jsonify(status)

    except Exception as e:
        logger.error(f"Failed to get market intelligence status: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
