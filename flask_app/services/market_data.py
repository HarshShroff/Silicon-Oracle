import logging
from typing import Any, Dict, Optional

from flask_app.services.oracle_service import OracleService
from flask_app.services.stock_service import StockService

logger = logging.getLogger(__name__)


class MarketDataService:
    """
    Service for fetching market data specifically for the Sentinel engine.
    Wraps StockService and OracleService to provide a unified interface.
    """

    def __init__(self, config: Optional[Dict[str, str]] = None):
        self.stock_service = StockService(config)
        self.oracle_service = OracleService(config)

    def get_market_status(self) -> Dict[str, Any]:
        """Check if the market is currently open."""
        return self.stock_service.get_market_status()

    def get_ticker_data(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Fetch all necessary data for a ticker in one go.
        Returns:
            - current_price
            - oracle_score
            - earnings_date
        """
        try:
            # Get Oracle Score (which fetches most data anyway)
            oracle_result = self.oracle_service.calculate_oracle_score(ticker)

            # Extract relevant fields
            current_price = 0.0
            quote = oracle_result.get("quote")
            if quote:
                current_price = quote.get("current", 0.0)

            # If no price from oracle (unlikely), try simpler fetch
            if current_price == 0:
                quote = self.stock_service.get_realtime_quote(ticker)
                if quote:
                    current_price = quote.get("current", 0.0)

            # Fetch earnings separately since OracleService doesn't expose the raw earnings object
            earnings_data = self.stock_service.get_earnings(ticker)

            return {
                "price": current_price,
                "score": oracle_result.get("score", 0),
                "confidence": oracle_result.get("confidence", 0),
                "verdict": oracle_result.get("verdict", "N/A"),
                "verdict_text": oracle_result.get("verdict_text", "N/A"),
                "earnings": earnings_data,
            }

        except Exception as e:
            logger.error(f"Error fetching sentinel data for {ticker}: {e}")
            return None
