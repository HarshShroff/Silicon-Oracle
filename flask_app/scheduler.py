from flask_apscheduler import APScheduler
import logging
import os

scheduler = APScheduler()
logger = logging.getLogger(__name__)


def sentinel_job():
    """
    Background job for Portfolio Sentinel.
    Runs every 30 mins to monitor positions.
    """
    from flask import current_app
    from flask_app.services.sentinel_engine import SentinelEngine
    from utils import database as db

    try:
        engine = SentinelEngine(current_app)
        client = db.get_supabase_client()
        if client:
            users_res = client.table("user_profiles").select("id").execute()
            if users_res.data:
                for user in users_res.data:
                    try:
                        engine.run_cycle(user_id=user['id'])
                    except Exception as users_e:
                        logger.error(
                            f"Sentinel failed for user {user.get('id')}: {users_e}")
    except Exception as e:
        logger.error(f"Sentinel job failed: {e}")


def daily_digest_job():
    """
    Daily job to send portfolio summaries.
    Runs once a day after market close.
    """
    from flask import current_app
    from utils import database as db
    from flask_app.services.notifications_service import send_daily_digest
    from flask_app.services.portfolio_service import PortfolioService
    from flask_app.services.stock_service import StockService

    client = db.get_supabase_client()
    if not client:
        return

    try:
        users = client.table("user_profiles").select(
            "id, email, notifications_enabled").execute()
        for user_data in users.data:
            if not user_data.get("notifications_enabled"):
                continue

            user_id = user_data['id']
            # Fetch notification patterns
            prefs = db.get_notification_preferences(user_id)
            if not prefs.get("daily_digest", True):
                continue

            # Get user config for Gmail
            config = db.get_user_api_keys(user_id, decrypt=True)
            if not config.get("GMAIL_ADDRESS") or not config.get("GMAIL_APP_PASSWORD"):
                continue

            # Prepare Digest Data
            # Note: In a real app we'd fetch live data here.
            # Using PortfolioService to get recent stats.
            portfolio_service = PortfolioService(user_id)
            metrics = portfolio_service.get_performance_metrics()

            # Simple summary object for the template
            summary = {
                # Mock total value for demo
                "total_value": metrics.get("total_realized_pnl", 0) + 10000,
                "days_pnl": metrics.get("total_realized_pnl", 0),
                "days_pnl_percent": (metrics.get("total_realized_pnl", 0) / 10000) * 100 if 10000 > 0 else 0
            }

            # Market status
            stock_service = StockService(config)
            market_status = stock_service.get_market_status()

            # Top opportunities
            top_opps = db.get_scan_results(user_id, limit=5)

            send_daily_digest(
                target_email=user_data['email'],
                app_password=config.get("GMAIL_APP_PASSWORD"),
                portfolio_summary=summary,
                top_opportunities=top_opps,
                market_status=market_status,
                sender_email=config.get("GMAIL_ADDRESS")
            )
            logger.info(
                f"Daily digest sent to {user_data['email']} (via {config.get('GMAIL_ADDRESS')})")

    except Exception as e:
        logger.error(f"Daily digest job failed: {e}")


def init_scheduler(app):
    """Initialize scheduler with jobs."""
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        # Sentinel Job: Every 5 minutes during market hours
        scheduler.add_job(
            id='sentinel_monitor',
            func=sentinel_job,
            trigger='cron',
            day_of_week='mon-fri',
            hour='9-16',
            minute='*/5',
            misfire_grace_time=300
        )

        # Daily Digest: Once a day at 5:00 PM
        scheduler.add_job(
            id='daily_digest_job',
            func=daily_digest_job,
            trigger='cron',
            day_of_week='mon-fri',
            hour='17',
            minute='0',
            misfire_grace_time=3600
        )

        logger.info("Background jobs scheduled.")
