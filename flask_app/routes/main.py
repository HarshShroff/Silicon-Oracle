"""
Silicon Oracle - Main Routes
Page rendering routes
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g
from functools import wraps
from flask_app.services import (
    StockService,
    OracleService,
    ScannerService,
    TradingService,
    PortfolioService,
)
from flask_app.services.scanner_service import WATCHLISTS

main_bp = Blueprint("main", __name__)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not g.user or not g.user.is_authenticated:
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def get_config():
    """
    Get API config from current user (BYOK - Bring Your Own Keys).
    Users MUST provide their own API keys. No fallback to app config.
    """
    from utils import database as db

    # If user is authenticated, get their API keys from database (decrypted)
    if g.user and g.user.is_authenticated:
        user_keys = db.get_user_api_keys(g.user.id, decrypt=True)
        return {
            "FINNHUB_API_KEY": user_keys.get("FINNHUB_API_KEY", ""),
            "ALPACA_API_KEY": user_keys.get("ALPACA_API_KEY", ""),
            "ALPACA_SECRET_KEY": user_keys.get("ALPACA_SECRET_KEY", ""),
            "GEMINI_API_KEY": user_keys.get("GEMINI_API_KEY", ""),
        }

    # No user logged in - return empty config
    return {
        "FINNHUB_API_KEY": "",
        "ALPACA_API_KEY": "",
        "ALPACA_SECRET_KEY": "",
        "GEMINI_API_KEY": "",
    }


@main_bp.route("/health")
def health():
    """Health check endpoint for monitoring."""
    return {"status": "ok", "service": "silicon-oracle"}, 200


@main_bp.route("/")
@login_required
def index():
    """Dashboard home page."""
    return redirect(url_for("main.analysis", ticker="NVDA"))


@main_bp.route("/analysis")
@main_bp.route("/analysis/<ticker>")
@login_required
def analysis(ticker="NVDA"):
    """Stock analysis page."""
    ticker = ticker.upper()
    config = get_config()

    try:
        stock_service = StockService(config)
        from flask_app.services.enhanced_oracle_service import EnhancedOracleService
        oracle_service = EnhancedOracleService(config)

        # Get complete data
        stock_data = stock_service.get_complete_data(ticker)
        oracle_result = oracle_service.calculate_enhanced_oracle_score(ticker)
    except Exception as e:
        # Provide empty data on error
        stock_data = {"ticker": ticker, "error": str(e)}
        oracle_result = {
            "ticker": ticker,
            "confidence": 0,
            "verdict": "ERROR",
            "verdict_text": "Error",
            "verdict_detail": str(e),
            "score": 0,
            "max_score": 0,
            "factors": [],
            "available_factors": 0,
            "total_factors": 0,
        }
        flash(f"Error loading data for {ticker}: {e}", "error")

    return render_template(
        "pages/analysis.html",
        ticker=ticker,
        stock_data=stock_data,
        oracle=oracle_result,
        watchlists=WATCHLISTS,
    )


@main_bp.route("/scanner")
@login_required
def scanner():
    """Market scanner page."""
    config = get_config()
    scanner_service = ScannerService(config)

    watchlist_name = request.args.get("watchlist", "AI/Tech")
    tickers = scanner_service.get_watchlist_tickers(watchlist_name)

    # Only scan if requested
    results = []
    if request.args.get("scan"):
        results = scanner_service.scan_watchlist(tickers)

    return render_template(
        "pages/scanner.html",
        watchlists=WATCHLISTS,
        selected_watchlist=watchlist_name,
        tickers=tickers,
        results=results,
    )


@main_bp.route("/portfolio")
@login_required
def portfolio():
    """Portfolio management page."""
    config = get_config()
    trading_service = TradingService(config)
    portfolio_service = PortfolioService(g.user.id)

    # Get Alpaca data if connected
    account = None
    alpaca_positions = []
    if trading_service.is_connected():
        account = trading_service.get_account()
        alpaca_positions = trading_service.get_positions()

    # Get local data
    trades = portfolio_service.get_trade_history(limit=50)
    metrics = portfolio_service.get_performance_metrics()
    history = portfolio_service.get_account_history(limit=30)

    return render_template(
        "pages/portfolio.html",
        account=account,
        positions=alpaca_positions,
        trades=trades,
        metrics=metrics,
        history=history,
        is_connected=trading_service.is_connected(),
    )


@main_bp.route("/trade")
@main_bp.route("/trade/<ticker>")
@login_required
def trade(ticker="NVDA"):
    """Trade execution page."""
    ticker = ticker.upper()
    config = get_config()

    stock_service = StockService(config)
    trading_service = TradingService(config)

    quote = stock_service.get_realtime_quote(ticker)
    account = trading_service.get_account() if trading_service.is_connected() else None
    position = (
        trading_service.get_position(
            ticker) if trading_service.is_connected() else None
    )
    orders = (
        trading_service.get_orders(status="open")
        if trading_service.is_connected()
        else []
    )

    return render_template(
        "pages/trade.html",
        ticker=ticker,
        quote=quote,
        account=account,
        position=position,
        orders=orders,
        is_connected=trading_service.is_connected(),
    )


@main_bp.route("/ai-guidance")
@login_required
def ai_guidance():
    """AI Guidance page with Oracle scanning. Quantitative factors load first."""
    return render_template("pages/ai_guidance.html")


@main_bp.route("/watchlist")
@login_required
def watchlist():
    """Watchlist management page."""
    config = get_config()
    scanner_service = ScannerService(config)
    trading_service = TradingService(config)

    selected = request.args.get("list", "AI/Tech")
    tickers = scanner_service.get_watchlist_tickers(selected)

    # Quick scan
    results = []
    if tickers:
        results = scanner_service.scan_watchlist(tickers)

    # Alpaca watchlists
    alpaca_lists = []
    if trading_service.is_connected():
        alpaca_lists = trading_service.get_watchlists()

    return render_template(
        "pages/watchlist.html",
        watchlists=WATCHLISTS,
        selected=selected,
        results=results,
        alpaca_lists=alpaca_lists,
        is_connected=trading_service.is_connected(),
    )


@main_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    """
    Settings page for API keys, email, and data export.
    BYOK (Bring Your Own Keys) - All API keys are user-provided and stored in Supabase.
    """
    from flask import jsonify
    from utils import database as db

    if request.method == "POST":
        user_id = g.user.id

        # Handle different form submissions
        if "save_api_keys" in request.form:
            # Save API keys to Supabase (BYOK) with encryption
            api_keys_data = {
                "alpaca_api_key": request.form.get("alpaca_key", "").strip(),
                "alpaca_secret_key": request.form.get("alpaca_secret", "").strip(),
                "finnhub_api_key": request.form.get("finnhub_key", "").strip(),
                "gemini_api_key": request.form.get("gemini_key", "").strip(),
            }

            # save_user_api_keys will handle encryption
            success = db.save_user_api_keys(user_id, api_keys_data)
            if success:
                flash("API keys saved successfully!", "success")
                return jsonify({"success": True})
            else:
                return jsonify({"success": False, "error": "Failed to save API keys"})

        elif "save_email" in request.form:
            # Save email settings to Supabase with encryption
            from utils.encryption import encrypt_value

            email_data = {
                "gmail_address": request.form.get("gmail_address", "").strip(),
                "notifications_enabled": True,
            }

            # Only update password if provided
            gmail_password = request.form.get("gmail_password", "").strip()
            if gmail_password:
                email_data["gmail_app_password_encrypted"] = encrypt_value(
                    gmail_password)

            # Save notification preferences to simulation_settings
            # Align with frontend keys: alert_price, alert_positions, alert_daily_digest
            notification_prefs = {
                "price_alerts": "alert_price" in request.form,
                "news_alerts": "alert_positions" in request.form,
                "daily_digest": "alert_daily_digest" in request.form,
                "email_alerts": True,  # Global toggle
            }

            db.update_user_profile(user_id, email_data)
            db.update_simulation_settings(user_id, notification_prefs)

            flash("Email settings saved successfully!", "success")
            return jsonify({"success": True})

        elif "test_connections" in request.form:
            # Test API connections
            config = {
                "ALPACA_API_KEY": request.form.get("alpaca_key", "").strip(),
                "ALPACA_SECRET_KEY": request.form.get("alpaca_secret", "").strip(),
                "FINNHUB_API_KEY": request.form.get("finnhub_key", "").strip(),
                "GEMINI_API_KEY": request.form.get("gemini_key", "").strip(),
            }

            trading_service = TradingService(config)
            stock_service = StockService(config)

            results = {}
            try:
                # Test Alpaca
                if trading_service.is_connected():
                    results["Alpaca"] = {
                        "success": True,
                        "message": "Connected successfully",
                    }
                else:
                    results["Alpaca"] = {
                        "success": False,
                        "error": "Invalid credentials",
                    }
            except Exception as e:
                results["Alpaca"] = {"success": False, "error": str(e)}

            try:
                # Test Finnhub
                quote = stock_service.get_realtime_quote("AAPL")
                if quote and quote.get("source") == "finnhub":
                    results["Finnhub"] = {
                        "success": True,
                        "message": "Connected successfully",
                    }
                else:
                    results["Finnhub"] = {
                        "success": False, "error": "Invalid API key"}
            except Exception as e:
                results["Finnhub"] = {"success": False, "error": str(e)}

            # Note: Gemini is tested on-demand during AI analysis
            results["Gemini"] = {
                "success": True,
                "message": "Will be tested during AI analysis",
            }

            return jsonify(results)

        elif "test_email" in request.form:
            # Test email configuration
            from flask_app.services.notifications_service import test_email_config

            result = test_email_config(
                request.form.get("gmail_address", "").strip(),
                request.form.get("gmail_password", "").strip(),
            )
            return jsonify(result)

    # GET request - render settings page
    # Fetch from database (BYOK)
    user_keys = db.get_user_api_keys(g.user.id, decrypt=True)
    notif_prefs = db.get_notification_preferences(g.user.id)

    return render_template(
        "pages/settings.html",
        alpaca_key=user_keys.get("ALPACA_API_KEY", ""),
        alpaca_secret=user_keys.get("ALPACA_SECRET_KEY", ""),
        finnhub_key=user_keys.get("FINNHUB_API_KEY", ""),
        gemini_key=user_keys.get("GEMINI_API_KEY", ""),
        gmail_address=user_keys.get("GMAIL_ADDRESS", ""),
        alert_price=notif_prefs.get("price_alerts", False),
        alert_positions=notif_prefs.get("news_alerts", False),
        alert_daily_digest=notif_prefs.get("daily_digest", False),
    )


@main_bp.route("/settings/load")
@login_required
def load_settings():
    """Load settings from session via AJAX."""
    return jsonify(
        {
            "api_keys": {
                "alpaca_key": session.get("alpaca_key", ""),
                "alpaca_secret": session.get("alpaca_secret", ""),
                "finnhub_key": session.get("finnhub_key", ""),
                "gemini_key": session.get("gemini_key", ""),
            },
            "email_settings": {
                "gmail_address": session.get("gmail_address", ""),
                "gmail_password": session.get("gmail_password", ""),
                "alert_price": session.get("alert_price", False),
                "alert_ai_signals": session.get("alert_ai_signals", False),
                "alert_positions": session.get("alert_positions", False),
                "alert_daily_digest": session.get("alert_daily_digest", False),
            },
        }
    )


@main_bp.route("/settings/data-summary")
@login_required
def data_summary():
    """Get data summary for export page."""
    portfolio_service = PortfolioService(g.user.id)

    # Get summary statistics
    trades = portfolio_service.get_trade_history(limit=1000)
    positions = portfolio_service.get_positions()

    summary = {
        "watchlists": len(session.get("user_watchlists", {})),
        "trades": len(trades),
        "positions": len(positions),
        "scan_results": len(
            [
                r
                for w in session.get("user_watchlists", {}).values()
                for r in w.get("results", [])
            ]
        ),
    }

    return jsonify(summary)


@main_bp.route("/settings/export")
@login_required
def export_data():
    """Export user data as CSV or Excel."""
    from flask import Response
    import pandas as pd
    from io import StringIO
    from datetime import datetime

    format_type = request.args.get("format", "csv").lower()

    try:
        portfolio_service = PortfolioService(g.user.id)

        # Collect all data
        data = {}

        # Settings
        data["settings"] = pd.DataFrame(
            [
                {"key": k, "value": str(v) if k != "gmail_password" else "***"}
                for k, v in {
                    "alpaca_key": session.get("alpaca_key", ""),
                    "finnhub_key": session.get("finnhub_key", ""),
                    "gemini_key": session.get("gemini_key", ""),
                    "gmail_address": session.get("gmail_address", ""),
                    "alert_price": session.get("alert_price", False),
                    "alert_ai_signals": session.get("alert_ai_signals", False),
                    "alert_positions": session.get("alert_positions", False),
                    "alert_daily_digest": session.get("alert_daily_digest", False),
                }.items()
            ]
        )

        # Trades
        trades = portfolio_service.get_trade_history(limit=1000)
        if trades:
            data["trades"] = pd.DataFrame(trades)

        # Positions
        positions = portfolio_service.get_positions()
        if positions:
            data["positions"] = pd.DataFrame(positions)

        # Watchlists
        user_watchlists = session.get("user_watchlists", {})
        if user_watchlists:
            watchlist_data = []
            for name, wl_data in user_watchlists.items():
                for ticker in wl_data.get("tickers", []):
                    watchlist_data.append(
                        {
                            "watchlist_name": name,
                            "ticker": ticker,
                            "created_at": wl_data.get("created_at", ""),
                        }
                    )

            if watchlist_data:
                data["watchlists"] = pd.DataFrame(watchlist_data)

        # Create output based on format
        if format_type == "excel":
            from io import BytesIO

            output = BytesIO()

            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                for sheet_name, df in data.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=False)

            output.seek(0)

            response = Response(
                output.getvalue(),
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={
                    "Content-Disposition": f"attachment; filename=silicon_oracle_export_{datetime.now().strftime('%Y%m%d')}.xlsx"
                },
            )
        else:
            # CSV export
            output = StringIO()

            for sheet_name, df in data.items():
                output.write(f"--- {sheet_name} ---\n")
                df.to_csv(output, index=False)
                output.write("\n\n")

            response = Response(
                output.getvalue(),
                mimetype="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=silicon_oracle_export_{datetime.now().strftime('%Y%m%d')}.csv"
                },
            )

        return response

    except Exception as e:
        return jsonify({"error": f"Export failed: {str(e)}"}), 500
