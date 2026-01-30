"""
Silicon Oracle - Portfolio Service
Handles local position tracking using Supabase for user isolation.
"""

import logging
from typing import Dict, Any, List, Optional
from utils import database as db

logger = logging.getLogger(__name__)


class PortfolioService:
    """Service for managing portfolio data with Supabase backend."""

    def __init__(self, user_id: str):
        self.user_id = user_id

    def get_positions(self) -> List[Dict[str, Any]]:
        """Get all positions for the current user."""
        if not self.user_id:
            return []
        return db.get_user_positions(self.user_id)

    def get_trade_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get user-specific trade history."""
        if not self.user_id:
            return []

        trades = db.get_user_trades(self.user_id, limit=limit)

        return [{
            'ticker': t.get('ticker'),
            'action': t.get('action'),
            'shares': t.get('shares'),
            'price': t.get('price'),
            'total_value': t.get('total_value') or (t.get('shares', 0) * t.get('price', 0)),
            'reason': t.get('reason'),
            'timestamp': t.get('timestamp'),
            'source': t.get('source', 'manual')
        } for t in trades]

    def add_trade(self, ticker: str, action: str, shares: float, price: float,
                  reason: str = None, order_id: str = None, source: str = 'manual') -> bool:
        """Record a user-specific trade."""
        if not self.user_id:
            return False

        client = db.get_supabase_client()
        if not client:
            return False

        try:
            total = shares * price
            client.table("trades").insert({
                "user_id": self.user_id,
                "ticker": ticker.upper(),
                "action": action.upper(),
                "shares": shares,
                "price": price,
                "total_value": total,
                "reason": reason,
                "order_id": order_id,
                "source": source
            }).execute()

            # Update position too
            if action.upper() == 'BUY':
                db.upsert_position(self.user_id, ticker, shares, price)

            return True
        except Exception as e:
            logger.error(f"Error adding trade: {e}")
            return False

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Calculate performance metrics for the user."""
        trades = self.get_trade_history(limit=1000)

        if not trades:
            return {'total_trades': 0, 'wins': 0, 'losses': 0, 'win_rate': 0, 'total_realized_pnl': 0}

        ticker_trades = {}
        for t in trades:
            ticker = t['ticker']
            if ticker not in ticker_trades:
                ticker_trades[ticker] = []
            ticker_trades[ticker].append(t)

        wins = 0
        losses = 0
        total_pnl = 0

        for ticker, ticker_list in ticker_trades.items():
            buys = [t for t in ticker_list if t['action'] == 'BUY']
            sells = [t for t in ticker_list if t['action'] == 'SELL']

            if buys and sells:
                sum_shares_buy = sum(t['shares'] for t in buys)
                sum_shares_sell = sum(t['shares'] for t in sells)

                if sum_shares_buy > 0 and sum_shares_sell > 0:
                    avg_buy = sum(t['price'] * t['shares']
                                  for t in buys) / sum_shares_buy
                    avg_sell = sum(t['price'] * t['shares']
                                   for t in sells) / sum_shares_sell

                    pnl = (avg_sell - avg_buy) * \
                        min(sum_shares_buy, sum_shares_sell)
                    total_pnl += pnl
                    if pnl > 0:
                        wins += 1
                    else:
                        losses += 1

        total = wins + losses
        return {
            'total_trades': len(trades),
            'wins': wins,
            'losses': losses,
            'win_rate': (wins / total * 100) if total > 0 else 0,
            'total_realized_pnl': total_pnl
        }

    def get_account_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get account value history from Supabase."""
        if not self.user_id:
            return []
        return db.get_account_history(self.user_id, limit=limit)

    def snapshot_account(self, portfolio_value: float, cash: float, buying_power: float, equity: float):
        """Save an account balance snapshot to Supabase."""
        if not self.user_id:
            return False
        return db.record_account_snapshot(
            self.user_id,
            cash=cash,
            buying_power=buying_power,
            portfolio_value=portfolio_value,
            equity=equity
        )
