"""
Sentinel Dashboard UI Routes
Provides the simulation/sentinel monitoring dashboard interface.
"""

from flask import Blueprint, render_template, jsonify, current_app, request, g
from utils import database as db
from flask_app.services.market_data import MarketDataService
from datetime import datetime

sentinel_ui_bp = Blueprint("sentinel_ui", __name__)


def get_user_id():
    """Helper to get user_id from request or session."""
    user_id = request.args.get("user_id")
    if not user_id and hasattr(g, 'user') and g.user:
        user_id = g.user.id
    return user_id


@sentinel_ui_bp.route("/sentinel/debug")
def debug_info():
    """Debug endpoint to check user and database state."""
    try:
        user_id = request.args.get("user_id")
        if not user_id and hasattr(g, 'user') and g.user:
            user_id = g.user.id

        positions = db.get_shadow_positions(user_id, is_active=True)

        return jsonify(
            {
                "status": "ok",
                "user_id": user_id,
                "positions_count": len(positions),
                "positions": positions,
            }
        )
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@sentinel_ui_bp.route("/simulation")
def simulation():
    """
    Render the Sentinel Dashboard / Simulation Mode page.
    Initial data is loaded via JavaScript from the API endpoints.
    """
    user_id = request.args.get("user_id")
    if not user_id and hasattr(g, 'user') and g.user:
        user_id = g.user.id

    position_count = len(db.get_shadow_positions(user_id, is_active=True))

    return render_template("pages/simulation.html", position_count=position_count)


@sentinel_ui_bp.route("/sentinel/positions/enriched")
def get_enriched_positions():
    """
    Get all positions with live market data enrichment.
    This provides real-time prices, P&L calculations, and alert status.
    """
    from flask_app.services.alert_engine import AlertEngine

    try:
        user_id = request.args.get("user_id")
        if not user_id and hasattr(g, 'user') and g.user:
            user_id = g.user.id

        positions = db.get_shadow_positions(user_id, is_active=True)

        if not positions:
            return jsonify(
                {
                    "positions": [],
                    "summary": {
                        "total_value": 0,
                        "total_cost": 0,
                        "total_pnl": 0,
                        "total_pnl_percent": 0,
                        "active_alerts": 0,
                    },
                }
            )

        if user_id:
            user_config = db.get_user_api_keys(user_id, decrypt=True)
        else:
            user_config = {}

        market_data = MarketDataService(user_config)
        alert_engine = AlertEngine()

        enriched_positions = []
        total_value = 0
        total_cost = 0
        active_alerts = 0

        for position in positions:
            ticker_data = market_data.get_ticker_data(position["ticker"])
            is_live = ticker_data is not None

            if ticker_data:
                live_price = ticker_data.get(
                    "price", position["average_entry_price"])
                oracle_score = ticker_data.get(
                    "score", position.get("last_oracle_score") or 0
                )
                oracle_confidence = ticker_data.get("confidence", 0)
                oracle_verdict = ticker_data.get("verdict_text", "N/A")
                earnings = ticker_data.get("earnings", {})
            else:
                live_price = position["average_entry_price"]
                oracle_score = position.get("last_oracle_score") or 0
                oracle_confidence = 0
                oracle_verdict = "N/A"
                earnings = {}

            company_name = f"{position['ticker']} (Info unavailable)"
            try:
                from flask_app.services.stock_service import StockService

                stock_svc = StockService(user_config)
                company_info = stock_svc.get_company_info(position["ticker"])
                if company_info and isinstance(company_info, dict):
                    company_name = company_info.get(
                        "name", f"{position['ticker']} (Info unavailable)")
            except Exception as e:
                current_app.logger.error(
                    f"Failed to get company info for {position['ticker']}: {e}"
                )

            position_value = live_price * position["quantity"]
            position_cost = position["average_entry_price"] * \
                position["quantity"]
            unrealized_pnl = position_value - position_cost
            unrealized_pnl_percent = (
                (
                    (live_price - position["average_entry_price"])
                    / position["average_entry_price"]
                    * 100
                )
                if position["average_entry_price"] > 0
                else 0
            )

            alerts = (
                alert_engine.check_position(position, ticker_data)
                if ticker_data
                else []
            )
            has_alert = len(alerts) > 0
            if has_alert:
                active_alerts += len(alerts)

            status = "Active"
            if earnings and isinstance(earnings, dict) and earnings.get("next_date"):
                from datetime import datetime, timedelta

                try:
                    next_earnings = datetime.fromisoformat(
                        str(earnings["next_date"]).replace("Z", "")
                    )
                    if next_earnings - datetime.utcnow() < timedelta(days=7):
                        status = "Earnings Soon"
                except:
                    pass

            # Convert any date objects to ISO format strings for JSON serialization
            for key, value in list(position.items()):
                if hasattr(value, 'isoformat'):
                    position[key] = value.isoformat()

            position.update(
                {
                    "live_price": live_price,
                    "oracle_score": oracle_score,
                    "oracle_confidence": oracle_confidence,
                    "oracle_verdict": oracle_verdict,
                    "position_value": position_value,
                    "position_cost": position_cost,
                    "unrealized_pnl": unrealized_pnl,
                    "unrealized_pnl_percent": unrealized_pnl_percent,
                    "has_alert": has_alert,
                    "alerts": alerts,
                    "status": status,
                    "next_earnings": earnings.get("next_date") if earnings else None,
                    "company_name": company_name,
                    "is_live": is_live,
                }
            )

            enriched_positions.append(position)
            total_value += position_value
            total_cost += position_cost

        total_pnl = total_value - total_cost
        total_pnl_percent = (
            ((total_value - total_cost) / total_cost * 100) if total_cost > 0 else 0
        )

        return jsonify(
            {
                "positions": enriched_positions,
                "summary": {
                    "total_value": total_value,
                    "total_cost": total_cost,
                    "total_pnl": total_pnl,
                    "total_pnl_percent": total_pnl_percent,
                    "active_alerts": active_alerts,
                    "position_count": len(enriched_positions),
                },
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sentinel_ui_bp.route("/sentinel/position/<int:position_id>", methods=["DELETE"])
def delete_position(position_id):
    """Delete/deactivate a position from Sentinel monitoring."""
    try:
        user_id = get_user_id()

        success = db.delete_shadow_position(position_id, user_id)
        if not success:
            return jsonify({"error": "Position not found or could not be deleted"}), 404

        return jsonify(
            {"message": "Position removed from Sentinel", "position_id": position_id}
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================
# NEWS ENDPOINTS
# ============================================


@sentinel_ui_bp.route("/sentinel/news")
def get_holdings_news():
    """Get aggregated news for all holdings."""
    try:
        user_id = get_user_id()
        positions = db.get_shadow_positions(user_id, is_active=True)

        if not positions:
            return jsonify({"news": [], "count": 0})

        tickers = [p["ticker"] for p in positions]

        # Get user config for API keys
        user_config = db.get_user_api_keys(
            user_id, decrypt=True) if user_id else {}

        from flask_app.services.news_monitor import NewsMonitor
        from flask_app.services.stock_service import StockService

        stock_service = StockService(user_config)
        news_monitor = NewsMonitor(stock_service)

        news = news_monitor.get_news_for_holdings(tickers, limit_per_ticker=5)

        return jsonify({
            "news": news[:20],  # Top 20 news items
            "count": len(news),
            "tickers": tickers
        })

    except Exception as e:
        current_app.logger.error(f"Error fetching news: {e}")
        return jsonify({"error": str(e)}), 500


@sentinel_ui_bp.route("/sentinel/news/breaking")
def get_breaking_news():
    """Get breaking/important news from the last 24 hours."""
    try:
        user_id = get_user_id()
        positions = db.get_shadow_positions(user_id, is_active=True)

        if not positions:
            return jsonify({"news": [], "count": 0})

        tickers = [p["ticker"] for p in positions]
        user_config = db.get_user_api_keys(
            user_id, decrypt=True) if user_id else {}

        from flask_app.services.news_monitor import NewsMonitor
        from flask_app.services.stock_service import StockService

        stock_service = StockService(user_config)
        news_monitor = NewsMonitor(stock_service)

        breaking = news_monitor.get_breaking_news(tickers, hours_back=24)

        return jsonify({
            "news": breaking,
            "count": len(breaking)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================
# SIMULATION SETTINGS ENDPOINTS
# ============================================


@sentinel_ui_bp.route("/sentinel/settings", methods=["GET"])
def get_settings():
    """Get simulation settings and notification preferences."""
    try:
        user_id = get_user_id()
        if not user_id:
            return jsonify({"error": "User not authenticated"}), 401

        settings = db.get_simulation_settings(user_id)

        # Return defaults if no settings exist
        if not settings:
            settings = {
                "starting_capital": 50.0,
                "current_cash": 0.0,
                "email_alerts": True,
                "price_alerts": True,
                "news_alerts": True,
                "daily_digest": True,
                "alert_threshold_percent": 5.0,
                "digest_time": "08:00"
            }

        return jsonify(settings)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sentinel_ui_bp.route("/sentinel/settings", methods=["POST"])
def update_settings():
    """Update simulation settings and notification preferences."""
    try:
        user_id = get_user_id()
        if not user_id:
            return jsonify({"error": "User not authenticated"}), 401

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Validate and sanitize input
        allowed_fields = [
            "starting_capital", "current_cash",
            "email_alerts", "price_alerts", "news_alerts", "daily_digest",
            "alert_threshold_percent", "digest_time"
        ]

        settings = {k: v for k, v in data.items() if k in allowed_fields}

        success = db.update_simulation_settings(user_id, settings)

        if success:
            return jsonify({"message": "Settings updated successfully"})
        else:
            return jsonify({"error": "Failed to update settings"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sentinel_ui_bp.route("/sentinel/history", methods=["GET"])
def get_history():
    """Get performance history for the simulation portfolio."""
    try:
        user_id = get_user_id()
        if not user_id:
            return jsonify({"error": "User not authenticated"}), 401

        limit = request.args.get("limit", 100, type=int)
        history = db.get_sentinel_history(user_id, limit=limit)

        # If no history exists, attempt to backfill the last 24h for an immediate graph
        if not history or len(history) < 3:
            backfill = generate_history_backfill(user_id)
            if backfill:
                # Merge: Current live history (if any) + backfill
                return jsonify(history + backfill)

        return jsonify(history)

    except Exception as e:
        current_app.logger.error(f"Error in sentinel history endpoint: {e}")
        return jsonify({"error": str(e)}), 500


def generate_history_backfill(user_id: str) -> list:
    """
    Generate a historical performance view for the last 24 hours 
    based on current holdings.
    """
    try:
        positions = db.get_shadow_positions(user_id, is_active=True)
        if not positions:
            return []

        settings = db.get_simulation_settings(user_id)
        current_cash = settings.get("current_cash", 50.0) if settings else 50.0
        starting_cap = settings.get(
            "starting_capital", 50.0) if settings else 50.0

        user_config = db.get_user_api_keys(user_id, decrypt=True)
        from flask_app.services.stock_service import StockService
        stock_service = StockService(user_config)

        all_hist = {}
        for pos in positions:
            # Get 2 days of 5-minute data for a higher resolution backfill
            df = stock_service.get_historical_data(
                pos["ticker"], period="2d", interval="5m")
            if df is not None and not df.empty:
                all_hist[pos["ticker"]] = df

        if not all_hist:
            return []

        # Common timeline from the first available ticker
        first_ticker = list(all_hist.keys())[0]
        timeline = all_hist[first_ticker].index.tolist()

        backfill_data = []
        # Go from most recent to oldest to match the client's expectation
        for ts in reversed(timeline):
            market_val = 0
            for pos in positions:
                ticker = pos["ticker"]
                if ticker in all_hist and ts in all_hist[ticker].index:
                    price = float(all_hist[ticker].loc[ts, 'Close'])
                    market_val += price * pos["quantity"]
                else:
                    market_val += pos["average_entry_price"] * pos["quantity"]

            total_val = market_val + current_cash
            backfill_data.append({
                "timestamp": ts.isoformat(),
                "total_value": total_val,
                "market_value": market_val,
                "cash": current_cash,
                "pnl": total_val - starting_cap
            })

        return backfill_data
    except Exception as e:
        current_app.logger.error(f"Backfill generation failed: {e}")
        return []


# ============================================
# EMAIL NOTIFICATION ENDPOINTS
# ============================================


@sentinel_ui_bp.route("/sentinel/test-email", methods=["POST"])
def test_email_notification():
    """Send a test email notification."""
    try:
        user_id = get_user_id()
        if not user_id:
            return jsonify({"error": "User not authenticated"}), 401

        # Get user profile for email
        profile = db.get_user_profile(user_id)
        if not profile or not profile.get("email"):
            return jsonify({"error": "User email not found"}), 400

        # Get API keys for email service
        user_config = db.get_user_api_keys(user_id, decrypt=True)
        if not user_config.get("gmail_address") or not user_config.get("gmail_app_password_encrypted"):
            return jsonify({
                "error": "Email not configured. Please add Gmail credentials in Settings."
            }), 400

        from flask_app.services.email_service import EmailService

        # Note: In production, you'd decrypt the password here
        email_service = EmailService({
            "gmail_address": user_config.get("gmail_address"),
            # Would be decrypted
            "gmail_app_password": user_config.get("gmail_app_password_encrypted")
        })

        success = email_service.send_email(
            to_email=profile["email"],
            subject="Test Notification - Silicon Oracle",
            html_body="""
            <html>
            <body style="font-family: Arial, sans-serif; background-color: #0f172a; color: #e2e8f0; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background-color: #1e293b; border-radius: 12px; padding: 24px;">
                    <h1 style="color: #22c55e;">✅ Test Successful!</h1>
                    <p>Your Silicon Oracle email notifications are working correctly.</p>
                    <p>You'll receive alerts for:</p>
                    <ul>
                        <li>Price movements exceeding your threshold</li>
                        <li>Breaking news for your holdings</li>
                        <li>Earnings alerts</li>
                        <li>Daily portfolio digests</li>
                    </ul>
                    <p style="margin-top: 24px; font-size: 12px; color: #64748b;">
                        Silicon Oracle - AI-Powered Stock Monitoring
                    </p>
                </div>
            </body>
            </html>
            """,
            text_body="Test notification from Silicon Oracle. Your email alerts are working!"
        )

        if success:
            return jsonify({"message": f"Test email sent to {profile['email']}"})
        else:
            return jsonify({"error": "Failed to send test email"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sentinel_ui_bp.route("/sentinel/send-digest", methods=["POST"])
def send_manual_digest():
    """Manually trigger a portfolio digest email."""
    try:
        user_id = get_user_id()
        if not user_id:
            return jsonify({"error": "User not authenticated"}), 401

        profile = db.get_user_profile(user_id)
        if not profile or not profile.get("email"):
            return jsonify({"error": "User email not found"}), 400

        user_config = db.get_user_api_keys(user_id, decrypt=True)
        if not user_config.get("gmail_address"):
            return jsonify({"error": "Email not configured"}), 400

        # Get portfolio data
        positions = db.get_shadow_positions(user_id, is_active=True)
        if not positions:
            return jsonify({"error": "No positions to report"}), 400

        # Enrich positions with live data
        market_data = MarketDataService(user_config)
        enriched = []
        total_value = 0
        total_cost = 0

        for pos in positions:
            ticker_data = market_data.get_ticker_data(pos["ticker"])
            if ticker_data:
                live_price = ticker_data.get(
                    "price", pos["average_entry_price"])
            else:
                live_price = pos["average_entry_price"]

            pos_value = live_price * pos["quantity"]
            pos_cost = pos["average_entry_price"] * pos["quantity"]

            enriched.append({
                "ticker": pos["ticker"],
                "live_price": live_price,
                "unrealized_pnl": pos_value - pos_cost,
                "unrealized_pnl_percent": ((live_price - pos["average_entry_price"]) / pos["average_entry_price"] * 100) if pos["average_entry_price"] > 0 else 0
            })

            total_value += pos_value
            total_cost += pos_cost

        # Get news
        from flask_app.services.news_monitor import NewsMonitor
        from flask_app.services.stock_service import StockService

        stock_service = StockService(user_config)
        news_monitor = NewsMonitor(stock_service)
        tickers = [p["ticker"] for p in positions]
        news = news_monitor.get_news_for_holdings(tickers, limit_per_ticker=3)

        # Send digest
        from flask_app.services.email_service import EmailService

        email_service = EmailService({
            "gmail_address": user_config.get("gmail_address"),
            "gmail_app_password": user_config.get("gmail_app_password_encrypted")
        })

        summary = {
            "total_value": total_value,
            "total_cost": total_cost,
            "total_pnl": total_value - total_cost,
            "position_count": len(enriched)
        }

        success = email_service.send_daily_digest(
            to_email=profile["email"],
            positions=enriched,
            news_items=news[:5],
            portfolio_summary=summary
        )

        if success:
            return jsonify({"message": f"Digest sent to {profile['email']}"})
        else:
            return jsonify({"error": "Failed to send digest"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================
# BULK IMPORT ENDPOINT
# ============================================


@sentinel_ui_bp.route("/sentinel/import", methods=["POST"])
def import_positions():
    """
    Bulk import positions (simulating Robinhood import).
    Accepts an array of positions with ticker, quantity, and entry price.
    """
    try:
        user_id = get_user_id()
        if not user_id:
            return jsonify({"error": "User not authenticated"}), 401

        data = request.get_json()
        if not data or not isinstance(data.get("positions"), list):
            return jsonify({"error": "Invalid data format. Expected {positions: []}"}), 400

        positions = data.get("positions", [])
        starting_capital = data.get("starting_capital", 50.0)

        # Update starting capital in settings
        db.update_simulation_settings(
            user_id, {"starting_capital": starting_capital})

        imported = 0
        errors = []

        for pos in positions:
            if not all(k in pos for k in ["ticker", "quantity", "average_entry_price"]):
                errors.append(f"Missing required fields for position: {pos}")
                continue

            try:
                position_data = {
                    "ticker": pos["ticker"].upper(),
                    "quantity": float(pos["quantity"]),
                    "average_entry_price": float(pos["average_entry_price"]),
                    "highest_price_seen": float(pos["average_entry_price"]),
                    "is_active": True
                }

                if db.add_shadow_position(user_id, position_data):
                    imported += 1
                else:
                    errors.append(f"Failed to import {pos['ticker']}")

            except Exception as e:
                errors.append(
                    f"Error importing {pos.get('ticker', 'unknown')}: {str(e)}")

        return jsonify({
            "message": f"Imported {imported} of {len(positions)} positions",
            "imported": imported,
            "errors": errors if errors else None
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sentinel_ui_bp.route("/sentinel/test-alert", methods=["POST"])
def test_sentinel_alert():
    """Manual trigger to test email alert plumbing."""
    from flask import current_app
    from datetime import datetime

    try:
        user_id = get_user_id()
        if not user_id:
            return jsonify({"error": "User not authenticated"}), 401

        # Initialize engine to get handle_alerts
        from flask_app.services.sentinel_engine import SentinelEngine
        engine = SentinelEngine(current_app)
        engine.user_id = user_id

        # Create dummy alert
        test_alerts = [{
            "type": "TEST_ALERT",
            "priority": "LOW",
            "message": "This is a test alert from Portfolio Sentinel. Your email plumbing is working!",
            "details": {"timestamp": datetime.now().isoformat()}
        }]

        # Helper position
        test_position = {"ticker": "TEST", "user_id": user_id}

        # Dispatch
        engine._handle_alerts(test_position, test_alerts)

        return jsonify({"success": True, "message": "Test alert sent"})

    except Exception as e:
        current_app.logger.error(f"Test alert failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
