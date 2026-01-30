"""
Silicon Oracle - Trading Service
Alpaca Paper Trading Integration (Streamlit-free)
"""

import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)


class TradingService:
    """Service for paper trading via Alpaca API."""

    def __init__(self, config: Dict[str, str] = None):
        self.config = config or {}
        self.trading_client = None
        self._initialize()

    def _initialize(self):
        """Initialize Alpaca API connection."""
        try:
            from alpaca.trading.client import TradingClient

            api_key = self.config.get('ALPACA_API_KEY')
            secret_key = self.config.get('ALPACA_SECRET_KEY')

            if api_key and secret_key:
                self.trading_client = TradingClient(
                    api_key=api_key,
                    secret_key=secret_key,
                    paper=True
                )
                logger.info("Alpaca client initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize Alpaca client: {e}")
            self.trading_client = None

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
                'buying_power': float(account.buying_power),
                'portfolio_value': float(account.portfolio_value),
                'cash': float(account.cash),
                'equity': float(account.equity),
                'currency': account.currency,
                'status': str(account.status)
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
            return [{
                'ticker': pos.symbol,
                'shares': float(pos.qty),
                'avg_price': float(pos.avg_entry_price),
                'current_price': float(pos.current_price),
                'market_value': float(pos.market_value),
                'unrealized_pl': float(pos.unrealized_pl),
                'unrealized_plpc': float(pos.unrealized_plpc) * 100,
                'side': pos.side
            } for pos in positions]
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
                'ticker': pos.symbol,
                'shares': float(pos.qty),
                'avg_price': float(pos.avg_entry_price),
                'current_price': float(pos.current_price),
                'unrealized_pl': float(pos.unrealized_pl),
                'unrealized_plpc': float(pos.unrealized_plpc) * 100
            }
        except Exception:
            return None

    def submit_order(self, ticker: str, qty: float, side: str,
                     order_type: str = 'market', limit_price: float = None) -> Dict[str, Any]:
        """Submit a trading order."""
        if not self.trading_client:
            return {'success': False, 'error': 'Not connected to Alpaca'}

        try:
            from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce

            ticker = ticker.upper()
            side_enum = OrderSide.BUY if side.lower() == 'buy' else OrderSide.SELL

            if order_type.lower() == 'market':
                req = MarketOrderRequest(
                    symbol=ticker,
                    qty=qty,
                    side=side_enum,
                    time_in_force=TimeInForce.DAY
                )
            else:
                req = LimitOrderRequest(
                    symbol=ticker,
                    qty=qty,
                    side=side_enum,
                    time_in_force=TimeInForce.DAY,
                    limit_price=limit_price
                )

            order = self.trading_client.submit_order(req)
            return {
                'success': True,
                'order_id': str(order.id),
                'status': str(order.status),
                'symbol': order.symbol,
                'qty': float(order.qty),
                'side': str(order.side)
            }
        except Exception as e:
            logger.error(f"Order submission failed: {e}")
            return {'success': False, 'error': str(e)}

    def buy(self, ticker: str, qty: float, order_type: str = 'market',
            limit_price: float = None) -> Dict[str, Any]:
        """Buy shares."""
        return self.submit_order(ticker, qty, 'buy', order_type, limit_price)

    def sell(self, ticker: str, qty: float, order_type: str = 'market',
             limit_price: float = None) -> Dict[str, Any]:
        """Sell shares."""
        return self.submit_order(ticker, qty, 'sell', order_type, limit_price)

    def close_position(self, ticker: str) -> Dict[str, Any]:
        """Close an entire position."""
        if not self.trading_client:
            return {'success': False, 'error': 'Not connected'}

        try:
            self.trading_client.close_position(ticker.upper())
            return {'success': True, 'message': f'Position {ticker} closed'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an order."""
        if not self.trading_client:
            return {'success': False, 'error': 'Not connected'}

        try:
            self.trading_client.cancel_order_by_id(order_id)
            return {'success': True, 'message': f'Order {order_id} cancelled'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_orders(self, status: str = 'open', limit: int = 20) -> List[Dict[str, Any]]:
        """Get orders by status."""
        if not self.trading_client:
            return []

        try:
            from alpaca.trading.requests import GetOrdersRequest
            from alpaca.trading.enums import QueryOrderStatus

            q_status = QueryOrderStatus.OPEN if status == 'open' else QueryOrderStatus.CLOSED
            req = GetOrdersRequest(status=q_status, limit=limit)
            orders = self.trading_client.get_orders(req)

            return [{
                'order_id': str(o.id),
                'ticker': o.symbol,
                'side': str(o.side).replace('OrderSide.', '').lower(),
                'qty': float(o.qty or 0),
                'filled_qty': float(o.filled_qty or 0),
                'status': str(o.status).replace('OrderStatus.', '').lower(),
                'type': str(o.type).replace('OrderType.', '').lower(),
                'submitted_at': str(o.submitted_at) if o.submitted_at else None,
                'filled_at': str(o.filled_at) if o.filled_at else None,
                'filled_avg_price': float(o.filled_avg_price or 0)
            } for o in orders]
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

    def get_portfolio_history(self, period: str = '1M',
                              timeframe: str = '1D') -> Optional[pd.DataFrame]:
        """Get portfolio equity history."""
        if not self.trading_client:
            return None

        try:
            from alpaca.trading.requests import GetPortfolioHistoryRequest

            req = GetPortfolioHistoryRequest(
                period=period,
                timeframe=timeframe,
                extended_hours=True
            )
            history = self.trading_client.get_portfolio_history(req)

            df = pd.DataFrame({
                'timestamp': history.timestamp,
                'equity': history.equity,
                'profit_loss': history.profit_loss,
                'profit_loss_pct': history.profit_loss_pct
            })

            df['timestamp'] = pd.to_datetime(
                df['timestamp'], unit='s', utc=True)
            df = df[df['equity'] > 0]

            return df if not df.empty else None
        except Exception as e:
            logger.error(f"Error getting portfolio history: {e}")
            return None

    def get_watchlists(self) -> List[Dict[str, Any]]:
        """Get all watchlists."""
        if not self.trading_client:
            return []

        try:
            watchlists = self.trading_client.get_watchlists()
            return [{
                'id': str(wl.id),
                'name': wl.name,
                'symbols': [asset.symbol for asset in (wl.assets or [])]
            } for wl in watchlists]
        except Exception as e:
            logger.error(f"Error getting watchlists: {e}")
            return []

    def create_watchlist(self, name: str, symbols: List[str] = None) -> Optional[Dict[str, Any]]:
        """Create a new watchlist."""
        if not self.trading_client:
            return None

        try:
            from alpaca.trading.requests import CreateWatchlistRequest

            req = CreateWatchlistRequest(name=name, symbols=symbols or [])
            wl = self.trading_client.create_watchlist(req)

            return {
                'id': str(wl.id),
                'name': wl.name,
                'symbols': [asset.symbol for asset in (wl.assets or [])]
            }
        except Exception as e:
            logger.error(f"Error creating watchlist: {e}")
            return None
