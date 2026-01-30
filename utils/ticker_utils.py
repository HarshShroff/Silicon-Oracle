"""
Ticker normalization utilities for Silicon Oracle.
Handles special cases like BRK.B, BF.B, etc.
"""


def normalize_ticker(ticker: str) -> str:
    """
    Normalize ticker symbol for API calls.

    yfinance uses hyphens (BRK-B), not dots (BRK.B)

    Examples:
        BRK.B -> BRK-B (yfinance format)
        brk.b -> BRK-B
        BRK-B -> BRK-B
    """
    if not ticker:
        return ticker

    # Convert to uppercase
    ticker = ticker.upper().strip()

    # Replace dots with hyphens (yfinance uses BRK-B, not BRK.B)
    ticker = ticker.replace('.', '-')

    return ticker


def is_valid_ticker(ticker: str) -> bool:
    """
    Check if ticker format is valid.

    Valid formats:
        - AAPL
        - BRK.B
        - GOOGL
    """
    if not ticker:
        return False

    ticker = ticker.strip().upper()

    # Basic validation: alphanumeric + dots only
    if not all(c.isalnum() or c == '.' for c in ticker):
        return False

    # Length check (1-10 characters)
    if len(ticker) < 1 or len(ticker) > 10:
        return False

    # Can't start or end with dot
    if ticker.startswith('.') or ticker.endswith('.'):
        return False

    return True
