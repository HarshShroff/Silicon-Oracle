import logging
from datetime import datetime
from flask import current_app
from utils import database as db
from flask_app.services.market_data import MarketDataService
from flask_app.services.alert_engine import AlertEngine

logger = logging.getLogger(__name__)


class SentinelEngine:
    """
    Core logic for the Portfolio Sentinel.
    Runs the monitoring loop, updates positions, and dispatches alerts.
    """

    def __init__(self, app=None):
        self.app = app
        self.market_data = None
        self.alert_engine = AlertEngine()
        self.user_id = None

    def run_cycle(self, user_id):
        """
        Execute one full monitoring cycle.
        """
        self.user_id = user_id
        # Ensure we are inside app context if not already
        if not current_app:
            if self.app:
                with self.app.app_context():
                    self._process_positions()
            else:
                logger.error("SentinelEngine needs flask app context!")
                return
        else:
            self._process_positions()

    def _init_services(self):
        """Lazy init services with current config."""
        if not self.market_data:
            # If user_id is present, try to fetch their specific keys (decrypted)
            user_config = {}
            if self.user_id:
                user_config = db.get_user_api_keys(self.user_id, decrypt=True)

            # STRICT ISOLATION: No fallback to system Config

            self.market_data = MarketDataService(user_config)

    def _process_positions(self):
        """Process all active positions for the current user."""
        if not self.user_id:
            logger.warning("Sentinel: No user id provided.")
            return

        self._init_services()

        # 1. Check Market Status
        try:
            status = self.market_data.get_market_status()
            if not status.get("is_open") and not current_app.config.get("DEBUG"):
                logger.info("Market closed. Sentinel sleeping.")
                return
        except Exception as e:
            logger.warning(
                f"Could not check market status: {e}. Proceeding anyway.")

        # 2. Fetch Active Positions from Supabase
        positions = db.get_shadow_positions(self.user_id, is_active=True)
        logger.info(f"Sentinel checking {len(positions)} positions...")

        total_market_value = 0.0
        for position in positions:
            try:
                market_value = self._analyze_position(position)
                if market_value:
                    total_market_value += market_value
            except Exception as e:
                logger.error(
                    f"Error processing position {position['ticker']}: {e}")

        # 3. Record Portfolio Snapshot for History Graph
        try:
            settings = db.get_simulation_settings(self.user_id)
            current_cash = settings.get(
                "current_cash", 0.0) if settings else 0.0
            total_value = total_market_value + current_cash

            # Simple P&L calculation
            starting_capital = settings.get(
                "starting_capital", 50.0) if settings else 50.0
            pnl = total_value - starting_capital

            db.record_sentinel_snapshot(self.user_id, {
                "total_value": total_value,
                "cash": current_cash,
                "market_value": total_market_value,
                "pnl": pnl
            })
            logger.info(
                f"Recorded sentinel snapshot for {self.user_id}: ${total_value:,.2f}")
        except Exception as e:
            logger.error(f"Error recording sentinel history snapshot: {e}")

    def _analyze_position(self, position):
        """Analyze a single position."""
        # Fetch Data
        data = self.market_data.get_ticker_data(position["ticker"])
        if not data:
            return

        current_price = data.get("price", 0.0)
        current_score = data.get("score", 0.0)

        # Check Alerts
        alerts = self.alert_engine.check_position(position, data)

        if alerts:
            self._handle_alerts(position, alerts)

        # Update Position Stats
        update_data = {}
        if current_price > position.get("highest_price_seen", 0.0):
            update_data["highest_price_seen"] = current_price

        if current_score:
            update_data["last_oracle_score"] = current_score

        if data.get("earnings") and data["earnings"].get("date"):
            try:
                earnings_date = datetime.strptime(
                    data["earnings"]["date"], "%Y-%m-%d"
                ).date()
                # Convert to ISO format string for JSON serialization
                update_data["next_earnings_date"] = earnings_date.isoformat()
            except:
                pass

        if update_data:
            db.update_shadow_position(
                position["id"], position["user_id"], update_data)

        return current_price * position["quantity"]

    def _handle_alerts(self, position, alerts):
        """Dispatch alerts."""
        if not alerts:
            return

        # Fetch user profile for email
        profile = db.get_user_profile(self.user_id)
        if not profile or not profile.get("notifications_enabled"):
            logger.info(f"Notifications disabled for user {self.user_id}")
            return

        # Fetch notification preferences
        prefs = db.get_notification_preferences(self.user_id)
        if not prefs.get("email_alerts", True):
            return

        # Fetch user config for Gmail credentials (decrypted)
        user_config = db.get_user_api_keys(self.user_id, decrypt=True)

        # Initialize Email Service
        from flask_app.services.email_service import EmailService
        email_service = EmailService({
            "gmail_address": user_config.get("GMAIL_ADDRESS"),
            "gmail_app_password": user_config.get("GMAIL_APP_PASSWORD")
        })

        if not email_service.is_configured():
            logger.warning(
                f"Email service not configured for user {self.user_id}")
            return

        # Prepare alert notification
        # Group alerts for this position
        logger.info(
            f"Dispatching {len(alerts)} alerts for {position['ticker']} to {profile['email']}")
        for alert in alerts:
            alert['ticker'] = position['ticker']
            msg = f"[{alert['priority']}] {position['ticker']}: {alert['message']}"
            logger.warning(f"SENTINEL ALERT: {msg}")

        # Send aggregated alert email
        email_service.send_alert_notification(
            to_email=profile["email"],
            alerts=alerts,
            portfolio_summary=None  # Could fetch if needed, but keeping it light for now
        )
