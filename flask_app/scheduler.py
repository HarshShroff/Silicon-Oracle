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


def market_intelligence_job():
    """
    Hourly AI-powered market intelligence job.
    Scans broad financial/geopolitical news and generates personalized stock recommendations.
    Uses Google Gemini AI with search grounding for comprehensive analysis.
    Only sends email if significant market developments and actionable recommendations exist.
    """
    from flask import current_app
    from utils import database as db
    from flask_app.services.market_intelligence_service import MarketIntelligenceService

    client = db.get_supabase_client()
    if not client:
        logger.warning("Supabase not available for market intelligence job")
        return

    try:
        # Get all users with news alerts enabled
        users = client.table("user_profiles").select(
            "id, email, notifications_enabled").execute()

        for user_data in users.data:
            if not user_data.get("notifications_enabled"):
                continue

            user_id = user_data['id']
            user_email = user_data['email']

            # Check if user wants news alerts
            prefs = db.get_notification_preferences(user_id)
            if not prefs.get("news_alerts", True):
                logger.info(f"User {user_email} has news alerts disabled")
                continue

            # Get user's API keys (required: Gmail, recommended: Gemini)
            config = db.get_user_api_keys(user_id, decrypt=True)
            if not config.get("GMAIL_ADDRESS") or not config.get("GMAIL_APP_PASSWORD"):
                logger.info(f"User {user_email} missing Gmail credentials")
                continue

            if not config.get("GEMINI_API_KEY"):
                logger.warning(f"User {user_email} missing Gemini API key - AI recommendations disabled")
                continue

            # Add Gmail credentials to config for email service
            config['gmail_address'] = config.get("GMAIL_ADDRESS")
            config['gmail_app_password'] = config.get("GMAIL_APP_PASSWORD")

            # Get user's shadow portfolio holdings
            holdings = db.get_shadow_positions(user_id, is_active=True)
            holding_tickers = [pos.get('ticker') for pos in holdings if pos.get('ticker')]

            # Get user's risk profile and available cash
            sim_settings = db.get_simulation_settings(user_id)
            risk_profile = sim_settings.get('risk_profile', 'moderate') if sim_settings else 'moderate'
            available_cash = sim_settings.get('current_cash', 0) if sim_settings else 0

            logger.info(f"Generating AI market intelligence for {user_email}")
            logger.info(f"  Holdings: {len(holding_tickers)}, Risk: {risk_profile}, Cash: ${available_cash:,.2f}")

            # Initialize market intelligence service
            intelligence_service = MarketIntelligenceService(config)

            # Generate comprehensive market intelligence and recommendations
            sent = intelligence_service.generate_market_intelligence(
                user_id=user_id,
                user_email=user_email,
                user_holdings=holding_tickers,
                risk_profile=risk_profile,
                available_cash=available_cash,
                hours_back=1
            )

            if sent:
                logger.info(f"✅ AI market intelligence email sent to {user_email}")
            else:
                logger.info(f"ℹ️ No significant market developments for {user_email} this hour")

    except Exception as e:
        logger.error(f"Market intelligence job failed: {e}", exc_info=True)


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

        # AI Market Intelligence: Every hour (24/7 for global markets)
        scheduler.add_job(
            id='market_intelligence_job',
            func=market_intelligence_job,
            trigger='cron',
            minute='0',  # Top of every hour
            misfire_grace_time=900  # 15 min grace period
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

        logger.info("Background jobs scheduled: Sentinel (5 min), AI Market Intelligence (hourly), Daily Digest (5 PM).")
