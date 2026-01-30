"""
Logging Configuration for Silicon Oracle

Provides centralized logging setup for debugging and monitoring.
Import get_logger() in any module to enable logging.
"""
import logging
import os
from datetime import datetime
from typing import Optional

# Log file path
LOG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(LOG_DIR, "silicon_oracle.log")

# Global flag to prevent multiple handler additions
_logging_configured = False


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    console_output: bool = True
) -> None:
    """
    Configure logging for the application.

    Args:
        level: Logging level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file (None to disable file logging)
        console_output: Whether to output to console/terminal
    """
    global _logging_configured

    if _logging_configured:
        return

    # Create formatters
    detailed_format = '%(asctime)s - %(levelname)s - %(name)s - %(funcName)s:%(lineno)d - %(message)s'
    simple_format = '%(levelname)s - %(name)s - %(message)s'

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers
    root_logger.handlers = []

    # File handler (detailed format)
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, mode='a')
            file_handler.setLevel(level)
            file_handler.setFormatter(logging.Formatter(detailed_format))
            root_logger.addHandler(file_handler)
        except Exception as e:
            print(f"Warning: Could not create log file: {e}")

    # Console handler (simple format)
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(logging.Formatter(simple_format))
        root_logger.addHandler(console_handler)

    _logging_configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module.

    Usage:
        from utils.logging_config import get_logger
        logger = get_logger(__name__)
        logger.info("Something happened")

    Args:
        name: Usually __name__ of the calling module

    Returns:
        Logger instance
    """
    # Ensure logging is configured
    if not _logging_configured:
        setup_logging(log_file=LOG_FILE)

    return logging.getLogger(name)


def log_function_call(logger: logging.Logger, func_name: str, **kwargs):
    """
    Log a function call with its arguments.

    Usage:
        log_function_call(logger, "calculate_oracle_score", ticker="NVDA")
    """
    args_str = ", ".join(f"{k}={v}" for k, v in kwargs.items())
    # logger.debug(f"CALL: {func_name}({args_str})")


def log_api_call(logger: logging.Logger, api_name: str, endpoint: str, success: bool, **kwargs):
    """
    Log an API call for debugging rate limits and failures.

    Usage:
        log_api_call(logger, "Finnhub", "/quote", success=True, ticker="NVDA")
    """
    status = "SUCCESS" if success else "FAILED"
    extra = ", ".join(f"{k}={v}" for k, v in kwargs.items())
    logger.info(f"API [{api_name}] {endpoint} - {status} - {extra}")


def log_user_action(logger: logging.Logger, action: str, details: Optional[str] = None):
    """
    Log a user action (for analytics/debugging).

    Usage:
        log_user_action(logger, "scan_started", "tickers=NVDA,AAPL")
    """
    msg = f"USER: {action}"
    if details:
        msg += f" - {details}"
    logger.info(msg)


def log_performance(logger: logging.Logger, operation: str, duration_ms: float):
    """
    Log performance metrics.

    Usage:
        start = time.time()
        # ... operation ...
        log_performance(logger, "oracle_scan", (time.time() - start) * 1000)
    """
    logger.info(f"PERF: {operation} completed in {duration_ms:.2f}ms")


# Convenience function to log errors with stack trace
def log_error_with_trace(logger: logging.Logger, message: str, exception: Exception):
    """
    Log an error with full stack trace.

    Usage:
        try:
            risky_operation()
        except Exception as e:
            log_error_with_trace(logger, "Operation failed", e)
    """
    logger.exception(f"ERROR: {message}")


# Initialize logging on module import
setup_logging(log_file=LOG_FILE)
