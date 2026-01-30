import logging
from typing import Dict, Any, Optional
from flask_app.services.stock_service import StockService
from flask_app.services.oracle_service import OracleService

logger = logging.getLogger(__name__)


class MarketDataService:
    """
    Service for fetching market data specifically for the Sentinel engine.
    Wraps StockService and OracleService to provide a unified interface.
    """

    def __init__(self, config: Dict[str, str] = None):
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
            quote = oracle_result.get('quote')
            if quote:
                current_price = quote.get('current', 0.0)

            # If no price from oracle (unlikely), try simpler fetch
            if current_price == 0:
                quote = self.stock_service.get_realtime_quote(ticker)
                if quote:
                    current_price = quote.get('current', 0.0)

            # Earnings date
            earnings_date = None
            earnings = oracle_result.get('company', {}).get(
                'earnings')  # generic path, check structure
            # Wait, OracleService uses data from StockService.get_complete_data
            # In StockService, earnings is 'earnings': lambda: self.get_earnings(ticker)
            # In OracleService, earnings = data.get('earnings')

            next_earnings = oracle_result.get('company', {}).get(
                'next_earnings_date')  # Checking if I need to dig deeper
            # Let's trust StockService's 'earnings' key if it flows through

            # Actually, OracleService doesn't pass 'earnings' raw dict to the final output except potentially via factors?
            # Looking at OracleService.calculate_oracle_score:
            # Returns dict with 'quote', 'company', etc.
            # But 'company' from StockService.get_company_info doesn't seem to include earnings date.
            # 'earnings' is a separate key in StockService.get_complete_data.

            # So I should probably re-fetch or rely on what OracleService returns.
            # OracleService uses 'earnings' to calculate factor 8.
            # It does NOT return the 'earnings' object in the final dictionary, only 'quote' and 'company'.

            # So I might need to fetch earnings separately if I want the exact date,
            # unless I modify OracleService to return it.
            # modifying OracleService is cleaner.

            # For now, I will use StockService explicitly for earnings to be safe.
            earnings_data = self.stock_service.get_earnings(ticker)

            return {
                'price': current_price,
                'score': oracle_result.get('score', 0),
                'confidence': oracle_result.get('confidence', 0),
                'verdict': oracle_result.get('verdict', 'N/A'),
                'verdict_text': oracle_result.get('verdict_text', 'N/A'),
                'earnings': earnings_data
            }

        except Exception as e:
            logger.error(f"Error fetching sentinel data for {ticker}: {e}")
            return None
