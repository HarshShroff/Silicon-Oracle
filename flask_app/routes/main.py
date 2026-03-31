"""
Silicon Oracle - Main Routes
Page rendering routes
"""

from functools import wraps

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from flask_app.extensions import limiter
from flask_app.services import (
    PortfolioService,
    ScannerService,
    StockService,
    TradingService,
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


def get_alpaca_enabled():
    """Read alpaca_enabled flag from session (source of truth) or DB."""
    from flask import session as _sess
    if 'alpaca_enabled' in _sess:
        return bool(_sess['alpaca_enabled'])
    from utils import database as db
    sim = db.get_simulation_settings(g.user.id) or {}
    val = sim.get("alpaca_enabled", None)
    return bool(val) if val is not None else True


def get_config():
    """
    Get API config from current user (BYOK - Bring Your Own Keys).
    Users MUST provide their own API keys. No fallback to app config.
    Respects alpaca_enabled flag — if disabled, Alpaca keys are omitted so
    TradingService.is_connected() returns False everywhere automatically.
    """
    from utils import database as db

    if g.user and g.user.is_authenticated:
        user_keys = db.get_user_api_keys(g.user.id, decrypt=True)
        alpaca_enabled = get_alpaca_enabled()
        return {
            "FINNHUB_API_KEY": user_keys.get("FINNHUB_API_KEY", ""),
            "ALPACA_API_KEY": user_keys.get("ALPACA_API_KEY", "") if alpaca_enabled else "",
            "ALPACA_SECRET_KEY": user_keys.get("ALPACA_SECRET_KEY", "") if alpaca_enabled else "",
            "GEMINI_API_KEY": user_keys.get("GEMINI_API_KEY", ""),
        }

    return {
        "FINNHUB_API_KEY": "",
        "ALPACA_API_KEY": "",
        "ALPACA_SECRET_KEY": "",
        "GEMINI_API_KEY": "",
    }


def get_shadow_portfolio(user_id, config):
    """Compute shadow portfolio positions + metrics for display when Alpaca is disabled."""
    from utils import database as db
    try:
        holdings = db.get_shadow_positions(user_id, is_active=True) or []
        if not holdings:
            return [], {}
        stock_service = StockService(config)
        positions = []
        total_value, total_cost = 0.0, 0.0
        for h in holdings:
            ticker = h.get("ticker", "")
            shares = float(h.get("shares") or 0)
            avg_price = float(h.get("avg_price") or 0)
            if not ticker or shares <= 0:
                continue
            try:
                quote = stock_service.get_realtime_quote(ticker)
                current_price = quote.get("current") or avg_price
            except Exception:
                current_price = avg_price
            pos_value = current_price * shares
            cost_basis = avg_price * shares
            total_value += pos_value
            total_cost += cost_basis
            positions.append({
                "ticker": ticker,
                "shares": shares,
                "avg_price": avg_price,
                "current_price": current_price,
                "market_value": pos_value,
                "unrealized_pl": pos_value - cost_basis,
                "unrealized_plpc": ((current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0,
            })
        total_pl = total_value - total_cost
        metrics = {
            "total_value": round(total_value, 2),
            "total_cost": round(total_cost, 2),
            "total_pl": round(total_pl, 2),
            "total_plpc": round((total_pl / total_cost * 100) if total_cost > 0 else 0, 2),
        }
        return positions, metrics
    except Exception:
        return [], {}


@main_bp.route("/health")
@limiter.exempt
def health():
    """Health check endpoint for monitoring."""
    return {"status": "ok", "service": "silicon-oracle"}, 200


@main_bp.route("/")
@login_required
def index():
    """Command Center home page."""
    return render_template("pages/command_center.html", alpaca_enabled=get_alpaca_enabled())


@main_bp.route("/command-center")
@login_required
def command_center():
    """Alias for index."""
    return render_template("pages/command_center.html", alpaca_enabled=get_alpaca_enabled())


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
        alpaca_enabled=get_alpaca_enabled(),
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
        alpaca_enabled=get_alpaca_enabled(),
    )


@main_bp.route("/portfolio")
@login_required
def portfolio():
    """Portfolio management page."""
    config = get_config()
    trading_service = TradingService(config)
    portfolio_service = PortfolioService(g.user.id)
    alpaca_enabled = get_alpaca_enabled()
    is_connected = trading_service.is_connected()

    # Alpaca data (only when connected)
    account = None
    alpaca_positions = []
    if is_connected:
        account = trading_service.get_account()
        alpaca_positions = trading_service.get_positions()

    # Shadow portfolio — always load; used as primary when Alpaca disabled
    shadow_positions, shadow_metrics = get_shadow_portfolio(g.user.id, config)

    # Positions to display: prefer Alpaca when connected, shadow otherwise
    display_positions = alpaca_positions if is_connected else shadow_positions

    trades = portfolio_service.get_trade_history(limit=50)
    metrics = portfolio_service.get_performance_metrics()
    history = portfolio_service.get_account_history(limit=30)

    return render_template(
        "pages/portfolio.html",
        account=account,
        positions=display_positions,
        shadow_metrics=shadow_metrics,
        trades=trades,
        metrics=metrics,
        history=history,
        is_connected=is_connected,
        alpaca_enabled=alpaca_enabled,
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
        alpaca_enabled=get_alpaca_enabled(),
    )


@main_bp.route("/ai-guidance")
@login_required
def ai_guidance():
    """AI Guidance page with Oracle scanning. Quantitative factors load first."""
    return render_template("pages/ai_guidance.html", alpaca_enabled=get_alpaca_enabled())


@main_bp.route("/watchlist")
@login_required
def watchlist():
    """Redirect to merged Scan & Watch page, watchlists tab."""
    return redirect(url_for('main.scanner') + '?tab=watchlists')


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
                # Bust user profile cache so next request re-fetches fresh keys
                from flask import current_app
                current_app._user_profile_cache.pop(f"user_{user_id}", None)
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

            # Only update password if provided and not a masked placeholder
            gmail_password = request.form.get("gmail_password", "").strip()
            if gmail_password and not gmail_password.startswith("***"):
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

        elif "save_alpaca_toggle" in request.form:
            from flask import session as flask_session
            enabled = request.form.get("alpaca_enabled") == "1"
            # Write to session immediately — works without any DB column
            flask_session['alpaca_enabled'] = enabled
            flask_session.modified = True
            # Best-effort DB save (works once migration adds the column)
            db.update_simulation_settings(user_id, {"alpaca_enabled": enabled})
            return jsonify({"success": True, "alpaca_enabled": enabled})

        elif "save_trading_style" in request.form:
            # Save trading style preference
            valid_styles = ("day_trading", "swing_trading", "long_term")
            trading_style = request.form.get("trading_style", "swing_trading").strip()
            if trading_style not in valid_styles:
                return jsonify({"success": False, "error": "Invalid trading style"})

            db.update_simulation_settings(user_id, {"trading_style": trading_style})
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
    sim_settings = db.get_simulation_settings(g.user.id) or {}

    # Mask gmail password like other API keys (show last 4 chars only)
    raw_gmail_pwd = user_keys.get("GMAIL_APP_PASSWORD", "")
    gmail_password_masked = ("***" + raw_gmail_pwd[-4:]) if raw_gmail_pwd and len(raw_gmail_pwd) > 4 else ""

    # Sync session with DB value on settings page load so both stay consistent
    from flask import session as flask_session
    db_alpaca_enabled = sim_settings.get("alpaca_enabled", None)
    if db_alpaca_enabled is not None:
        alpaca_enabled = bool(db_alpaca_enabled)
        flask_session['alpaca_enabled'] = alpaca_enabled
    elif 'alpaca_enabled' in flask_session:
        alpaca_enabled = bool(flask_session['alpaca_enabled'])
    else:
        alpaca_enabled = True

    return render_template(
        "pages/settings.html",
        alpaca_key=user_keys.get("ALPACA_API_KEY", ""),
        alpaca_secret=user_keys.get("ALPACA_SECRET_KEY", ""),
        finnhub_key=user_keys.get("FINNHUB_API_KEY", ""),
        gemini_key=user_keys.get("GEMINI_API_KEY", ""),
        gmail_address=user_keys.get("GMAIL_ADDRESS", ""),
        gmail_password_masked=gmail_password_masked,
        trading_style=sim_settings.get("trading_style", "swing_trading"),
        alpaca_enabled=alpaca_enabled,
        alert_price=notif_prefs.get("price_alerts", False),
        alert_positions=notif_prefs.get("news_alerts", False),
        alert_daily_digest=notif_prefs.get("daily_digest", False),
    )


@main_bp.route("/macro")
@login_required
def macro():
    """Macro Intelligence Dashboard — geopolitical events, portfolio impact, trade suggestions."""
    from flask import session as flask_session
    if 'alpaca_enabled' in flask_session:
        alpaca_enabled = bool(flask_session['alpaca_enabled'])
    else:
        from utils import database as db
        sim = db.get_simulation_settings(g.user.id) or {}
        val = sim.get("alpaca_enabled", None)
        alpaca_enabled = bool(val) if val is not None else True
    return render_template("pages/macro.html", alpaca_enabled=alpaca_enabled)


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
    from datetime import datetime
    from io import StringIO

    import pandas as pd
    from flask import Response

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


@main_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring and deployment verification."""
    from datetime import datetime

    from utils import database as db

    try:
        # Check database connection
        db.conn  # Access connection object to verify it exists

        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '2.1.0'
        }), 200
    except Exception as e:
        import logging
        logging.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 503
