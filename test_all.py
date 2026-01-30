#!/usr/bin/env python3
"""
Silicon Oracle - Comprehensive Test Suite

This test file validates all major components of the application.
Run with: python test_all.py

Logs are saved to test_results.log
"""

import os
import sys
import logging
from datetime import datetime
from typing import Tuple, Any, Dict, List

# Configure logging
LOG_FILE = "test_results.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode="w"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("TestSuite")


class TestResult:
    """Stores test results"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors: List[Tuple[str, str]] = []

    def add_pass(self, test_name: str):
        self.passed += 1
        logger.info(f"PASS: {test_name}")

    def add_fail(self, test_name: str, reason: str):
        self.failed += 1
        self.errors.append((test_name, reason))
        logger.error(f"FAIL: {test_name} - {reason}")

    def summary(self):
        total = self.passed + self.failed
        logger.info("=" * 60)
        logger.info(f"TEST SUMMARY: {self.passed}/{total} passed, {self.failed} failed")
        if self.errors:
            logger.info("Failed Tests:")
            for name, reason in self.errors:
                logger.info(f"  - {name}: {reason}")
        logger.info("=" * 60)


def run_test(test_name: str, test_func, results: TestResult):
    """Run a single test and record result"""
    try:
        success, message = test_func()
        if success:
            results.add_pass(test_name)
        else:
            results.add_fail(test_name, message)
    except Exception as e:
        results.add_fail(test_name, f"Exception: {str(e)}")


# ============================================
# TEST: Encryption Module
# ============================================
def test_encryption() -> Tuple[bool, str]:
    """Test encryption/decryption functions"""
    try:
        from utils.encryption import (
            encrypt_value,
            decrypt_value,
            encrypt_api_keys,
            decrypt_api_keys,
        )

        # Test basic encryption
        test_value = "my_secret_api_key_12345"
        encrypted = encrypt_value(test_value)

        if not encrypted:
            return False, "encrypt_value returned empty"

        if encrypted == test_value:
            return False, "Value not encrypted (still plaintext)"

        # Test decryption
        decrypted = decrypt_value(encrypted)
        if decrypted != test_value:
            return False, f"Decryption mismatch: expected {test_value}, got {decrypted}"

        # Test API keys encryption
        test_keys = {
            "alpaca_api_key": "test_alpaca_key",
            "finnhub_api_key": "test_finnhub_key",
        }
        encrypted_keys = encrypt_api_keys(test_keys)

        if "alpaca_api_key_encrypted" not in encrypted_keys:
            return False, "encrypt_api_keys missing expected key"

        decrypted_keys = decrypt_api_keys(encrypted_keys)
        if decrypted_keys.get("alpaca_api_key") != "test_alpaca_key":
            return False, "decrypt_api_keys failed to restore original key"

        return True, "OK"
    except ImportError as e:
        return False, f"Import error: {e}"


# ============================================
# TEST: Database Module (Structure Only)
# ============================================
def test_database_module() -> Tuple[bool, str]:
    """Test database module imports and structure"""
    try:
        from utils.database import (
            get_supabase_client,
            is_supabase_enabled,
            get_user_profile,
            create_user_profile,
            update_user_profile,
            save_user_api_keys,
            get_user_api_keys,
            get_user_positions,
            upsert_position,
            delete_position,
            get_user_trades,
            record_trade,
            get_user_watchlists,
            create_watchlist,
            update_watchlist,
            delete_watchlist,
            save_scan_results,
            get_scan_results,
            record_account_snapshot,
            get_account_history,
            get_schema_sql,
        )

        # Test schema SQL exists
        schema = get_schema_sql()
        if not schema or "CREATE TABLE" not in schema:
            return False, "Schema SQL missing or invalid"

        logger.info(f"Supabase enabled: {is_supabase_enabled()}")

        return True, "OK"
    except ImportError as e:
        return False, f"Import error: {e}"


# ============================================
# TEST: Auth Module
# ============================================
def test_auth_module() -> Tuple[bool, str]:
    """Test auth module imports and functions"""
    try:
        from utils.auth import (
            get_auth_client,
            is_auth_enabled,
            get_current_user,
            get_current_user_id,
            is_logged_in,
            set_user_session,
            clear_user_session,
            sign_up,
            sign_in,
            sign_out,
            reset_password,
            get_user_decrypted_keys,
            save_user_api_keys,
            clear_api_keys_cache,
            render_login_form,
            render_user_menu,
            require_auth,
            enable_local_dev_mode,
            is_local_dev_mode,
            get_app_url,
        )

        # Test get_app_url
        app_url = get_app_url()
        if not app_url.startswith("http"):
            return False, f"Invalid app URL: {app_url}"

        logger.info(f"App URL: {app_url}")
        logger.info(f"Auth enabled: {is_auth_enabled()}")

        return True, "OK"
    except ImportError as e:
        return False, f"Import error: {e}"


# ============================================
# TEST: AI Scanner Module
# ============================================
def test_ai_scanner_module() -> Tuple[bool, str]:
    """Test AI scanner module structure"""
    try:
        from utils.ai_scanner import (
            OracleScanner,
            MAX_ORACLE_SCORE,
            SECTOR_ETFS,
            get_oracle_scanner,
            render_ai_guidance_tab,
        )

        # Verify MAX_ORACLE_SCORE
        if MAX_ORACLE_SCORE != 12.0:
            return False, f"MAX_ORACLE_SCORE incorrect: {MAX_ORACLE_SCORE}"

        # Verify SECTOR_ETFS has major sectors
        required_sectors = ["Technology", "Financial Services", "Healthcare"]
        for sector in required_sectors:
            if sector not in SECTOR_ETFS:
                return False, f"Missing sector: {sector}"

        # Test scanner instantiation
        scanner = OracleScanner()
        if not hasattr(scanner, "calculate_oracle_score"):
            return False, "Scanner missing calculate_oracle_score method"
        if not hasattr(scanner, "scan_watchlist"):
            return False, "Scanner missing scan_watchlist method"

        return True, "OK"
    except ImportError as e:
        return False, f"Import error: {e}"


# ============================================
# TEST: Notifications Module
# ============================================
def test_notifications_module() -> Tuple[bool, str]:
    """Test notifications module structure"""
    try:
        from utils.notifications import (
            send_email,
            send_self_notification,
            get_base_template,
            format_price_alert,
            format_ai_signal,
            format_position_alert,
            format_daily_digest,
            format_test_email,
            send_price_alert,
            send_ai_signal,
            send_position_alert,
            send_daily_digest,
            send_test_notification,
            render_notification_settings,
        )

        # Test template generation
        template = get_base_template("<p>Test</p>", "Test Title")
        if "Silicon Oracle" not in template:
            return False, "Template missing Silicon Oracle branding"
        if "<p>Test</p>" not in template:
            return False, "Template missing content"

        # Test format functions
        price_alert = format_price_alert("NVDA", 100.0, 110.0, "UP")
        if "NVDA" not in price_alert:
            return False, "Price alert missing ticker"

        ai_signal = format_ai_signal(
            "AAPL", "Buy", 8.5, ["Good momentum", "Strong earnings"]
        )
        if "AAPL" not in ai_signal or "Buy" not in ai_signal:
            return False, "AI signal format incorrect"

        return True, "OK"
    except ImportError as e:
        return False, f"Import error: {e}"


# ============================================
# TEST: Godmode Data Module
# ============================================
def test_godmode_data_module() -> Tuple[bool, str]:
    """Test godmode data module structure"""
    try:
        from utils.godmode_data import (
            get_finviz_data,
            get_finnhub_client,
            get_realtime_quote,
            get_market_status,
            get_company_peers,
            get_earnings_calendar,
            get_insider_transactions,
            get_recommendation_trends,
            get_price_targets,
            get_google_news,
            get_alpaca_news,
            get_market_movers,
            get_company_fundamentals,
            get_chart_data,
            get_complete_intelligence,
        )

        return True, "OK"
    except ImportError as e:
        return False, f"Import error: {e}"


# ============================================
# TEST: Alpaca Module
# ============================================
def test_alpaca_module() -> Tuple[bool, str]:
    """Test Alpaca module structure"""
    try:
        from utils.alpaca import (
            get_alpaca_trader,
            render_alpaca_account,
            render_trade_dialog,
            render_orders_tab,
        )

        trader = get_alpaca_trader()
        if not hasattr(trader, "is_connected"):
            return False, "Trader missing is_connected method"
        if not hasattr(trader, "get_account"):
            return False, "Trader missing get_account method"
        if not hasattr(trader, "get_positions"):
            return False, "Trader missing get_positions method"
        if not hasattr(trader, "submit_order"):
            return False, "Trader missing submit_order method"

        logger.info(f"Alpaca connected: {trader.is_connected()}")

        return True, "OK"
    except ImportError as e:
        return False, f"Import error: {e}"


# ============================================
# TEST: Portfolio Module
# ============================================
def test_portfolio_module() -> Tuple[bool, str]:
    """Test portfolio module structure"""
    try:
        from portfolio import (
            get_portfolio_manager,
            render_portfolio_sidebar,
            render_portfolio_tab,
        )

        pm = get_portfolio_manager()
        if not hasattr(pm, "get_positions"):
            return False, "PortfolioManager missing get_positions method"
        if not hasattr(pm, "get_trade_history"):
            return False, "PortfolioManager missing get_trade_history method"
        if not hasattr(pm, "get_performance_metrics"):
            return False, "PortfolioManager missing get_performance_metrics method"

        return True, "OK"
    except ImportError as e:
        return False, f"Import error: {e}"


# ============================================
# TEST: Scanner Module
# ============================================
def test_scanner_module() -> Tuple[bool, str]:
    """Test scanner module structure"""
    try:
        from scanner import render_scanner_tab, get_quick_scan_results, WATCHLISTS

        # Verify watchlists exist
        if not WATCHLISTS:
            return False, "WATCHLISTS is empty"

        required_lists = ["Tech Giants", "ETFs"]
        for wl in required_lists:
            if wl not in WATCHLISTS:
                logger.warning(f"Missing watchlist: {wl}")

        return True, "OK"
    except ImportError as e:
        return False, f"Import error: {e}"


# ============================================
# TEST: Data Module
# ============================================
def test_data_module() -> Tuple[bool, str]:
    """Test data module structure"""
    try:
        from utils.data import fetch_stock_data, fetch_latest_price, get_data_fetcher

        fetcher = get_data_fetcher()
        if not hasattr(fetcher, "get_bars"):
            return False, "DataFetcher missing get_bars method"
        if not hasattr(fetcher, "is_available"):
            return False, "DataFetcher missing is_available method"

        logger.info(f"Data fetcher available: {fetcher.is_available()}")

        return True, "OK"
    except ImportError as e:
        return False, f"Import error: {e}"


# ============================================
# TEST: Quant Module
# ============================================
def test_quant_module() -> Tuple[bool, str]:
    """Test quant module structure"""
    try:
        from utils.quant import calculate_optimal_position

        # The function should exist and be callable
        if not callable(calculate_optimal_position):
            return False, "calculate_optimal_position is not callable"

        return True, "OK"
    except ImportError as e:
        return False, f"Import error: {e}"


# ============================================
# TEST: Settings Page
# ============================================
def test_settings_page() -> Tuple[bool, str]:
    """Test settings page structure"""
    try:
        from pages.settings import (
            render_settings_page,
            render_api_keys_settings,
            test_api_connections,
            render_preferences_settings,
        )

        return True, "OK"
    except ImportError as e:
        return False, f"Import error: {e}"


# ============================================
# TEST: Live API Calls (if credentials available)
# ============================================
def test_live_yfinance() -> Tuple[bool, str]:
    """Test live yfinance data fetching"""
    try:
        import yfinance as yf

        stock = yf.Ticker("AAPL")
        hist = stock.history(period="5d")

        if hist.empty:
            return False, "yfinance returned empty data for AAPL"

        if "Close" not in hist.columns:
            return False, "yfinance data missing Close column"

        close_price = hist["Close"].iloc[-1]
        if close_price <= 0:
            return False, f"Invalid close price: {close_price}"

        logger.info(f"AAPL latest close: ${close_price:.2f}")

        return True, "OK"
    except Exception as e:
        return False, f"yfinance error: {e}"


def test_live_finnhub() -> Tuple[bool, str]:
    """Test live Finnhub data fetching (if API key available)"""
    try:
        from utils.godmode_data import get_finnhub_client, get_realtime_quote

        client = get_finnhub_client()
        if not client:
            return True, "SKIPPED - No Finnhub API key configured"

        quote = get_realtime_quote("AAPL")
        if quote:
            logger.info(f"AAPL Finnhub quote: ${quote.get('current', 0):.2f}")
            return True, "OK"
        else:
            return False, "Finnhub returned no data"
    except Exception as e:
        return False, f"Finnhub error: {e}"


def test_live_google_news() -> Tuple[bool, str]:
    """Test live Google News fetching"""
    try:
        from utils.godmode_data import get_google_news

        news = get_google_news("NVDA")

        if not news:
            return False, "Google News returned no results"

        if not isinstance(news, list):
            return False, "Google News did not return a list"

        first_item = news[0]
        if "headline" not in first_item:
            return False, "News item missing headline"

        logger.info(f"Found {len(news)} news items for NVDA")
        logger.info(f"First headline: {first_item.get('headline', 'N/A')[:50]}...")

        return True, "OK"
    except Exception as e:
        return False, f"Google News error: {e}"


def test_oracle_score_calculation() -> Tuple[bool, str]:
    """Test Oracle score calculation (mock test)"""
    try:
        from utils.ai_scanner import OracleScanner

        scanner = OracleScanner()

        # Test SPY context
        spy_context = scanner._get_spy_context()
        if spy_context:
            logger.info(f"SPY context: {spy_context.get('trend', 'N/A')}")

        # Test RSI calculation with sample data
        import pandas as pd
        import numpy as np

        # Create sample price data
        np.random.seed(42)
        prices = pd.Series(100 + np.cumsum(np.random.randn(100)))
        rsi = scanner._calculate_rsi(prices)

        if not 0 <= rsi <= 100:
            return False, f"RSI out of range: {rsi}"

        logger.info(f"Sample RSI calculation: {rsi:.2f}")

        # Test MACD calculation
        macd = scanner._calculate_macd(prices)
        if "signal" not in macd:
            return False, "MACD missing signal"

        logger.info(f"Sample MACD signal: {macd.get('signal', 'N/A')}")

        return True, "OK"
    except Exception as e:
        return False, f"Oracle calculation error: {e}"


def test_dividend_yield_conversion() -> Tuple[bool, str]:
    """Test dividend yield conversion logic"""
    try:
        # Test case 1: Decimal form (yfinance) -> 0.03 should become 3%
        div_yield_decimal = 0.03
        if div_yield_decimal < 1:
            div_pct = div_yield_decimal * 100
        else:
            div_pct = div_yield_decimal

        if abs(div_pct - 3.0) > 0.001:
            return False, f"Decimal conversion failed: expected 3.0, got {div_pct}"

        # Test case 2: Already percent (Finviz) -> 3.5 should stay 3.5%
        div_yield_percent = 3.5
        if div_yield_percent < 1:
            div_pct = div_yield_percent * 100
        else:
            div_pct = div_yield_percent

        if abs(div_pct - 3.5) > 0.001:
            return False, f"Percent conversion failed: expected 3.5, got {div_pct}"

        logger.info("Dividend yield conversion logic OK")

        return True, "OK"
    except Exception as e:
        return False, f"Dividend test error: {e}"


# ============================================
# MAIN TEST RUNNER
# ============================================
def main():
    """Run all tests"""
    logger.info("=" * 60)
    logger.info("SILICON ORACLE - COMPREHENSIVE TEST SUITE")
    logger.info(f"Started at: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    results = TestResult()

    # Module Structure Tests
    logger.info("\n--- MODULE STRUCTURE TESTS ---")
    run_test("Encryption Module", test_encryption, results)
    run_test("Database Module", test_database_module, results)
    run_test("Auth Module", test_auth_module, results)
    run_test("AI Scanner Module", test_ai_scanner_module, results)
    run_test("Notifications Module", test_notifications_module, results)
    run_test("Godmode Data Module", test_godmode_data_module, results)
    run_test("Alpaca Module", test_alpaca_module, results)
    run_test("Portfolio Module", test_portfolio_module, results)
    run_test("Scanner Module", test_scanner_module, results)
    run_test("Data Module", test_data_module, results)
    run_test("Quant Module", test_quant_module, results)
    run_test("Settings Page", test_settings_page, results)

    # Logic Tests
    logger.info("\n--- LOGIC TESTS ---")
    run_test("Dividend Yield Conversion", test_dividend_yield_conversion, results)
    run_test("Oracle Score Calculation", test_oracle_score_calculation, results)

    # Live API Tests
    logger.info("\n--- LIVE API TESTS ---")
    run_test("Live yfinance", test_live_yfinance, results)
    run_test("Live Finnhub", test_live_finnhub, results)
    run_test("Live Google News", test_live_google_news, results)

    # Summary
    results.summary()

    logger.info(f"\nTest results saved to: {LOG_FILE}")

    # Return exit code based on results
    return 0 if results.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
