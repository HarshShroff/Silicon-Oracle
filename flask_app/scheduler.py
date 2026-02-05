from flask_apscheduler import APScheduler
import logging
import os
from datetime import datetime

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
            if user_data.get("notifications_enabled") is False:
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

            # Get shadow portfolio positions
            shadow_positions = db.get_shadow_positions(user_id, is_active=True)

            # Get current prices and build holdings list
            stock_service = StockService(config)
            holdings = []
            total_value = 0.0
            total_cost = 0.0

            for pos in shadow_positions:
                ticker = pos.get('ticker')
                quantity = pos.get('quantity', 0)
                entry_price = pos.get('average_entry_price', 0)
                if not ticker or quantity <= 0:
                    continue

                # Get current price via Finnhub
                quote = stock_service.get_realtime_quote(ticker)
                current_price = quote.get('current', entry_price) if quote else entry_price
                market_value = quantity * current_price
                cost_basis = quantity * entry_price
                pnl = market_value - cost_basis
                pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0

                holdings.append({
                    'ticker': ticker,
                    'shares': quantity,
                    'price': current_price,
                    'market_value': market_value,
                    'cost_basis': cost_basis,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct
                })
                total_value += market_value
                total_cost += cost_basis

            # Get simulation settings for cash
            sim_settings = db.get_simulation_settings(user_id)
            cash = sim_settings.get('current_cash', 0) if sim_settings else 0
            total_equity = total_value + cash
            total_pnl = total_value - total_cost

            summary = {
                "total_value": total_equity,
                "portfolio_value": total_value,
                "cash": cash,
                "days_pnl": total_pnl,
                "days_pnl_percent": (total_pnl / total_cost * 100) if total_cost > 0 else 0
            }

            # Market status
            market_status = stock_service.get_market_status()

            # Top opportunities
            top_opps = db.get_scan_results(user_id, limit=5)

            send_daily_digest(
                target_email=user_data['email'],
                app_password=config.get("GMAIL_APP_PASSWORD"),
                portfolio_summary=summary,
                top_opportunities=top_opps,
                market_status=market_status,
                sender_email=config.get("GMAIL_ADDRESS"),
                holdings=holdings
            )
            logger.info(
                f"Daily digest sent to {user_data['email']} (via {config.get('GMAIL_ADDRESS')})")

    except Exception as e:
        logger.error(f"Daily digest job failed: {e}")


def market_intelligence_job():
    """
    Hourly AI-powered market intelligence job (during market hours only).
    Runs every hour from 10 AM - 4 PM EST (Monday-Friday).
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
            if user_data.get("notifications_enabled") is False:
                continue

            user_id = user_data['id']
            user_email = user_data['email']

            # Check if user wants news alerts
            prefs = db.get_notification_preferences(user_id)
            if not prefs.get("news_alerts", True):
                logger.info(f"User {user_email} has news alerts disabled")
                continue

            # Check email frequency preference (hourly, daily, weekly)
            frequency = prefs.get("market_intel_frequency", "hourly")
            import pytz
            now_eastern = datetime.now(pytz.timezone('US/Eastern'))
            current_hour = now_eastern.hour
            current_day = now_eastern.weekday()  # 0=Monday, 6=Sunday

            if frequency == "daily" and current_hour != 10:  # Send at 10 AM EST (first market hour)
                continue
            elif frequency == "weekly" and (current_day != 0 or current_hour != 10):  # Monday 10 AM EST
                continue
            # If hourly, always send (every hour on the hour)

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

            trading_style = sim_settings.get('trading_style', 'swing_trading') if sim_settings else 'swing_trading'

            logger.info(f"Generating AI market intelligence for {user_email}")
            logger.info(f"  Holdings: {len(holding_tickers)}, Risk: {risk_profile}, Style: {trading_style}, Cash: ${available_cash:,.2f}")

            # Initialize market intelligence service
            intelligence_service = MarketIntelligenceService(config)

            # Generate comprehensive market intelligence and recommendations
            sent = intelligence_service.generate_market_intelligence(
                user_id=user_id,
                user_email=user_email,
                user_holdings=holding_tickers,
                risk_profile=risk_profile,
                available_cash=available_cash,
                hours_back=1,
                trading_style=trading_style
            )

            if sent:
                logger.info(f"✅ AI market intelligence email sent to {user_email}")
            else:
                logger.info(f"ℹ️ No significant market developments for {user_email} this hour")

    except Exception as e:
        logger.error(f"Market intelligence job failed: {e}", exc_info=True)


def market_close_summary_job():
    """
    Daily market close summary job (5 PM EST, Monday-Friday).
    Summarizes how the market performed today and impact on shadow portfolio holdings.
    Similar format to market intelligence but focused on today's performance.
    """
    from flask import current_app
    from utils import database as db
    from flask_app.services.market_intelligence_service import MarketIntelligenceService

    client = db.get_supabase_client()
    if not client:
        logger.warning("Supabase not available for market close summary job")
        return

    try:
        # Get all users with news alerts enabled
        users = client.table("user_profiles").select(
            "id, email, notifications_enabled").execute()

        for user_data in users.data:
            if user_data.get("notifications_enabled") is False:
                continue

            user_id = user_data['id']
            user_email = user_data['email']

            # Check if user wants daily digest
            prefs = db.get_notification_preferences(user_id)
            if not prefs.get("daily_digest", True):
                logger.info(f"User {user_email} has daily digest disabled")
                continue

            # Get user's API keys (required: Gmail, Gemini)
            config = db.get_user_api_keys(user_id, decrypt=True)
            if not config.get("GMAIL_ADDRESS") or not config.get("GMAIL_APP_PASSWORD"):
                logger.info(f"User {user_email} missing Gmail credentials")
                continue

            if not config.get("GEMINI_API_KEY"):
                logger.warning(f"User {user_email} missing Gemini API key")
                continue

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

            trading_style = sim_settings.get('trading_style', 'swing_trading') if sim_settings else 'swing_trading'

            logger.info(f"Generating market close summary for {user_email}")
            logger.info(f"  Holdings: {len(holding_tickers)}, Risk: {risk_profile}, Style: {trading_style}, Cash: ${available_cash:,.2f}")

            # Initialize market intelligence service
            intelligence_service = MarketIntelligenceService(config)

            # Generate market close summary
            sent = intelligence_service.generate_market_close_summary(
                user_id=user_id,
                user_email=user_email,
                user_holdings=holding_tickers,
                risk_profile=risk_profile,
                available_cash=available_cash,
                trading_style=trading_style
            )

            if sent:
                logger.info(f"✅ Market close summary sent to {user_email}")
            else:
                logger.info(f"ℹ️ No significant market developments for {user_email} today")

    except Exception as e:
        logger.error(f"Market close summary job failed: {e}", exc_info=True)


def market_preview_job():
    """
    Daily market preview job (9 AM EST, every day).
    Provides heads up for today's market and potential impact on shadow portfolio.
    Similar format to market intelligence but focused on what might happen today.
    """
    from flask import current_app
    from utils import database as db
    from flask_app.services.market_intelligence_service import MarketIntelligenceService

    client = db.get_supabase_client()
    if not client:
        logger.warning("Supabase not available for market preview job")
        return

    try:
        # Get all users with news alerts enabled
        users = client.table("user_profiles").select(
            "id, email, notifications_enabled").execute()

        for user_data in users.data:
            if user_data.get("notifications_enabled") is False:
                continue

            user_id = user_data['id']
            user_email = user_data['email']

            # Check if user wants news alerts
            prefs = db.get_notification_preferences(user_id)
            if not prefs.get("news_alerts", True):
                logger.info(f"User {user_email} has news alerts disabled")
                continue

            # Get user's API keys (required: Gmail, Gemini)
            config = db.get_user_api_keys(user_id, decrypt=True)
            if not config.get("GMAIL_ADDRESS") or not config.get("GMAIL_APP_PASSWORD"):
                logger.info(f"User {user_email} missing Gmail credentials")
                continue

            if not config.get("GEMINI_API_KEY"):
                logger.warning(f"User {user_email} missing Gemini API key")
                continue

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

            trading_style = sim_settings.get('trading_style', 'swing_trading') if sim_settings else 'swing_trading'

            logger.info(f"Generating market preview for {user_email}")
            logger.info(f"  Holdings: {len(holding_tickers)}, Risk: {risk_profile}, Style: {trading_style}, Cash: ${available_cash:,.2f}")

            # Initialize market intelligence service
            intelligence_service = MarketIntelligenceService(config)

            # Generate market preview
            sent = intelligence_service.generate_market_preview(
                user_id=user_id,
                user_email=user_email,
                user_holdings=holding_tickers,
                risk_profile=risk_profile,
                available_cash=available_cash,
                trading_style=trading_style
            )

            if sent:
                logger.info(f"✅ Market preview sent to {user_email}")
            else:
                logger.info(f"ℹ️ No significant market events expected for {user_email} today")

    except Exception as e:
        logger.error(f"Market preview job failed: {e}", exc_info=True)


def init_scheduler(app):
    """Initialize scheduler with jobs."""
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        # Sentinel Job: Every 5 minutes during market hours (9 AM - 4 PM EST)
        scheduler.add_job(
            id='sentinel_monitor',
            func=sentinel_job,
            trigger='cron',
            timezone='US/Eastern',
            day_of_week='mon-fri',
            hour='9-16',
            minute='*/5',
            misfire_grace_time=300
        )

        # AI Market Intelligence: Hourly during market hours (10 AM - 4 PM EST, Mon-Fri)
        scheduler.add_job(
            id='market_intelligence_job',
            func=market_intelligence_job,
            trigger='cron',
            timezone='US/Eastern',
            day_of_week='mon-fri',
            hour='10-16',
            minute='0',
            misfire_grace_time=900
        )

        # Market Preview: 9:00 AM EST Mon-Fri (heads up for the day)
        scheduler.add_job(
            id='market_preview_job',
            func=market_preview_job,
            trigger='cron',
            timezone='US/Eastern',
            day_of_week='mon-fri',
            hour='9',
            minute='0',
            misfire_grace_time=900
        )

        # Market Close Summary: 5:00 PM EST Mon-Fri (recap of today's performance)
        scheduler.add_job(
            id='market_close_summary_job',
            func=market_close_summary_job,
            trigger='cron',
            timezone='US/Eastern',
            day_of_week='mon-fri',
            hour='17',
            minute='0',
            misfire_grace_time=900
        )

        # Daily Digest: 5:30 PM EST Mon-Fri (after close summary)
        scheduler.add_job(
            id='daily_digest_job',
            func=daily_digest_job,
            trigger='cron',
            timezone='US/Eastern',
            day_of_week='mon-fri',
            hour='17',
            minute='30',
            misfire_grace_time=3600
        )

        logger.info("Background jobs scheduled: Sentinel (5 min), Market Preview (9 AM daily), AI Market Intel (10 AM-4 PM hourly), Market Close Summary (5 PM), Daily Digest (5:30 PM).")
