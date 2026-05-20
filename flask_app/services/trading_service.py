"""
Silicon Oracle - Trading Service
DEPRECATED: Alpaca paper trading integration has been removed.
trading_client is always None; all methods return safe empty values.
"""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class TradingService:
    """Stub trading service — Alpaca integration deprecated."""

    def __init__(self, config: Optional[Dict[str, str]] = None):
        self.config = config or {}
        self.trading_client = None
        self._initialize()

    def _initialize(self):
        # DEPRECATED: Alpaca removed. trading_client stays None.
        # from alpaca.trading.client import TradingClient
        # api_key = self.config.get("ALPACA_API_KEY")
        # secret_key = self.config.get("ALPACA_SECRET_KEY")
        # if api_key and secret_key:
        #     self.trading_client = TradingClient(api_key=api_key, secret_key=secret_key, paper=True)
        logger.debug("TradingService: Alpaca deprecated, trading_client=None")

    def is_connected(self) -> bool:
        """Check if Alpaca is connected."""
        return self.trading_client is not None

    def get_account(self) -> Optional[Dict[str, Any]]:
        """Get account information."""
        if not self.trading_client:
            return None

        try:
            account = self.trading_client.get_account()
            return {
                "buying_power": float(account.buying_power),
                "portfolio_value": float(account.portfolio_value),
                "cash": float(account.cash),
                "equity": float(account.equity),
                "currency": account.currency,
                "status": str(account.status),
            }
        except Exception as e:
            logger.error(f"Error getting account: {e}")
            return None

    def get_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions."""
        if not self.trading_client:
            return []

        try:
            positions = self.trading_client.get_all_positions()
            return [
                {
                    "ticker": pos.symbol,
                    "shares": float(pos.qty),
                    "avg_price": float(pos.avg_entry_price),
                    "current_price": float(pos.current_price),
                    "market_value": float(pos.market_value),
                    "unrealized_pl": float(pos.unrealized_pl),
                    "unrealized_plpc": float(pos.unrealized_plpc) * 100,
                    "side": pos.side,
                }
                for pos in positions
            ]
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    def get_position(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get position for a specific ticker."""
        if not self.trading_client:
            return None

        try:
            pos = self.trading_client.get_open_position(ticker.upper())
            return {
                "ticker": pos.symbol,
                "shares": float(pos.qty),
                "avg_price": float(pos.avg_entry_price),
                "current_price": float(pos.current_price),
                "unrealized_pl": float(pos.unrealized_pl),
                "unrealized_plpc": float(pos.unrealized_plpc) * 100,
            }
        except Exception:
            return None

    def submit_order(
        self,
        ticker: str,
        qty: float,
        side: str,
        order_type: str = "market",
        limit_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Submit a trading order."""
        if not self.trading_client:
            return {"success": False, "error": "Not connected to Alpaca"}

        try:
            raise RuntimeError("Alpaca integration deprecated")
        except Exception as e:
            logger.error(f"Order submission failed: {e}")
            return {"success": False, "error": str(e)}

    def buy(
        self,
        ticker: str,
        qty: float,
        order_type: str = "market",
        limit_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Buy shares."""
        return self.submit_order(ticker, qty, "buy", order_type, limit_price)

    def sell(
        self,
        ticker: str,
        qty: float,
        order_type: str = "market",
        limit_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Sell shares."""
        return self.submit_order(ticker, qty, "sell", order_type, limit_price)

    def close_position(self, ticker: str) -> Dict[str, Any]:
        """Close an entire position."""
        if not self.trading_client:
            return {"success": False, "error": "Not connected"}

        try:
            self.trading_client.close_position(ticker.upper())
            return {"success": True, "message": f"Position {ticker} closed"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an order."""
        if not self.trading_client:
            return {"success": False, "error": "Not connected"}

        try:
            self.trading_client.cancel_order_by_id(order_id)
            return {"success": True, "message": f"Order {order_id} cancelled"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_orders(self, status: str = "open", limit: int = 20) -> List[Dict[str, Any]]:
        """Get orders by status."""
        if not self.trading_client:
            return []

        try:
            raise RuntimeError("Alpaca integration deprecated")
        except Exception as e:
            logger.error(f"Error getting orders: {e}")
            return []

    def is_market_open(self) -> bool:
        """Check if market is open."""
        if not self.trading_client:
            return False

        try:
            clock = self.trading_client.get_clock()
            return clock.is_open
        except Exception:
            return False

    def get_portfolio_history(
        self, period: str = "1M", timeframe: str = "1D"
    ) -> Optional[pd.DataFrame]:
        """Get portfolio equity history."""
        if not self.trading_client:
            return None

        try:
            # DEPRECATED: Alpaca removed
            raise RuntimeError("Alpaca integration deprecated")
        except Exception as e:
            logger.error(f"Error getting portfolio history: {e}")
            return None

    def get_watchlists(self) -> List[Dict[str, Any]]:
        """Get all watchlists."""
        if not self.trading_client:
            return []

        try:
            watchlists = self.trading_client.get_watchlists()
            return [
                {
                    "id": str(wl.id),
                    "name": wl.name,
                    "symbols": [asset.symbol for asset in (wl.assets or [])],
                }
                for wl in watchlists
            ]
        except Exception as e:
            logger.error(f"Error getting watchlists: {e}")
            return []

    def create_watchlist(
        self, name: str, symbols: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a new watchlist."""
        if not self.trading_client:
            return None

        try:
            raise RuntimeError("Alpaca integration deprecated")
        except Exception as e:
            logger.error(f"Error creating watchlist: {e}")
            return None
