"""
Portfolio Manager - SQLite Database & Portfolio Logic
The "Brain" of Silicon Oracle
"""

import sqlite3
import streamlit as st
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import pandas as pd


class PortfolioManager:
    """Manages portfolio positions, trades, and cash using SQLite."""

    def __init__(self, db_path: str = "portfolio.db"):
        self.db_path = db_path
        # Add timeout to prevent "database is locked" errors
        self.conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30.0)
        self.conn.row_factory = sqlite3.Row  # Return rows as dicts
        # Use DELETE mode (safer than WAL when files get deleted)
        self.conn.execute("PRAGMA journal_mode=DELETE")
        self._init_database()

    def _init_database(self):
        """Create tables if they don't exist."""
        cursor = self.conn.cursor()

        # Portfolio settings (cash, starting capital)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value REAL
            )
        """)

        # Current positions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT UNIQUE NOT NULL,
                shares REAL NOT NULL,
                avg_price REAL NOT NULL,
                entry_date TEXT NOT NULL,
                last_updated TEXT NOT NULL
            )
        """)

        # Trade history (synced from Alpaca)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                action TEXT NOT NULL,  -- BUY, SELL
                shares REAL NOT NULL,
                price REAL NOT NULL,
                total_value REAL NOT NULL,
                reason TEXT,
                timestamp TEXT NOT NULL,
                alpaca_order_id TEXT,  -- Link to Alpaca order
                UNIQUE(alpaca_order_id)  -- Prevent duplicates
            )
        """)

        # Order history (full Alpaca order details)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alpaca_order_id TEXT UNIQUE NOT NULL,
                ticker TEXT NOT NULL,
                side TEXT NOT NULL,
                order_type TEXT,
                qty REAL NOT NULL,
                filled_qty REAL,
                filled_avg_price REAL,
                status TEXT NOT NULL,
                submitted_at TEXT,
                filled_at TEXT,
                synced_at TEXT NOT NULL
            )
        """)

        # Account history (track balance over time)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS account_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                cash REAL NOT NULL,
                buying_power REAL NOT NULL,
                portfolio_value REAL NOT NULL,
                equity REAL NOT NULL
            )
        """)

        # Initialize cash if not exists
        cursor.execute("""
            INSERT OR IGNORE INTO settings (key, value) VALUES ('cash', ?)
        """, (st.secrets.get("trading", {}).get("starting_capital", 500),))

        self.conn.commit()

    # --- CASH MANAGEMENT ---

    def get_cash(self) -> float:
        """Get current cash balance."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'cash'")
        result = cursor.fetchone()
        return result['value'] if result else 0.0

    def update_cash(self, amount: float):
        """Update cash balance."""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE settings SET value = ? WHERE key = 'cash'", (amount,))
        self.conn.commit()

    def add_cash(self, amount: float):
        """Add cash to balance."""
        current = self.get_cash()
        self.update_cash(current + amount)

    def subtract_cash(self, amount: float) -> bool:
        """Subtract cash from balance. Returns False if insufficient funds."""
        current = self.get_cash()
        if current >= amount:
            self.update_cash(current - amount)
            return True
        return False

    # --- POSITION MANAGEMENT ---

    def get_positions(self) -> List[Dict[str, Any]]:
        """Get all current positions."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM positions ORDER BY ticker")
        return [dict(row) for row in cursor.fetchall()]

    def get_position(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get a specific position."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM positions WHERE ticker = ?", (ticker.upper(),))
        result = cursor.fetchone()
        return dict(result) if result else None

    def add_position(self, ticker: str, shares: float, price: float) -> bool:
        """Add or update a position (buying more shares)."""
        ticker = ticker.upper()
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()

        existing = self.get_position(ticker)
        if existing:
            # Average down/up the position
            total_shares = existing['shares'] + shares
            total_cost = (existing['shares'] *
                          existing['avg_price']) + (shares * price)
            new_avg = total_cost / total_shares

            cursor.execute("""
                UPDATE positions
                SET shares = ?, avg_price = ?, last_updated = ?
                WHERE ticker = ?
            """, (total_shares, new_avg, now, ticker))
        else:
            # New position
            cursor.execute("""
                INSERT INTO positions (ticker, shares, avg_price, entry_date, last_updated)
                VALUES (?, ?, ?, ?, ?)
            """, (ticker, shares, price, now, now))

        self.conn.commit()
        return True

    def reduce_position(self, ticker: str, shares: float) -> bool:
        """Reduce a position (selling shares). Returns False if not enough shares."""
        ticker = ticker.upper()
        cursor = self.conn.cursor()

        existing = self.get_position(ticker)
        if not existing or existing['shares'] < shares:
            return False

        remaining = existing['shares'] - shares
        now = datetime.now().isoformat()

        if remaining <= 0.0001:  # Close position (handle float precision)
            cursor.execute("DELETE FROM positions WHERE ticker = ?", (ticker,))
        else:
            cursor.execute("""
                UPDATE positions SET shares = ?, last_updated = ? WHERE ticker = ?
            """, (remaining, now, ticker))

        self.conn.commit()
        return True

    # --- TRADE LOGGING ---

    def log_trade(self, ticker: str, action: str, shares: float, price: float, reason: str = None):
        """Log a trade to history."""
        cursor = self.conn.cursor()
        total_value = shares * price
        now = datetime.now().isoformat()

        cursor.execute("""
            INSERT INTO trades (ticker, action, shares, price, total_value, reason, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (ticker.upper(), action.upper(), shares, price, total_value, reason, now))

        self.conn.commit()

    def get_trade_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent trade history."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def get_trades_for_ticker(self, ticker: str) -> List[Dict[str, Any]]:
        """Get all trades for a specific ticker."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM trades WHERE ticker = ? ORDER BY timestamp DESC
        """, (ticker.upper(),))
        return [dict(row) for row in cursor.fetchall()]

    # --- TRADING OPERATIONS ---

    def buy(self, ticker: str, shares: float, price: float, reason: str = None) -> Dict[str, Any]:
        """Execute a buy order. Returns result dict."""
        ticker = ticker.upper()
        total_cost = shares * price

        if not self.subtract_cash(total_cost):
            return {
                "success": False,
                "error": f"Insufficient funds. Need ${total_cost:.2f}, have ${self.get_cash():.2f}"
            }

        self.add_position(ticker, shares, price)
        self.log_trade(ticker, "BUY", shares, price, reason)

        return {
            "success": True,
            "ticker": ticker,
            "shares": shares,
            "price": price,
            "total": total_cost,
            "cash_remaining": self.get_cash()
        }

    def sell(self, ticker: str, shares: float, price: float, reason: str = None) -> Dict[str, Any]:
        """Execute a sell order. Returns result dict."""
        ticker = ticker.upper()

        if not self.reduce_position(ticker, shares):
            position = self.get_position(ticker)
            current_shares = position['shares'] if position else 0
            return {
                "success": False,
                "error": f"Insufficient shares. Have {current_shares}, trying to sell {shares}"
            }

        total_proceeds = shares * price
        self.add_cash(total_proceeds)
        self.log_trade(ticker, "SELL", shares, price, reason)

        return {
            "success": True,
            "ticker": ticker,
            "shares": shares,
            "price": price,
            "total": total_proceeds,
            "cash_remaining": self.get_cash()
        }

    def sell_all(self, ticker: str, price: float, reason: str = None) -> Dict[str, Any]:
        """Sell entire position in a ticker."""
        position = self.get_position(ticker)
        if not position:
            return {"success": False, "error": f"No position in {ticker}"}

        return self.sell(ticker, position['shares'], price, reason)

    # --- ANALYTICS ---

    def get_portfolio_value(self, current_prices: Dict[str, float]) -> Dict[str, Any]:
        """Calculate total portfolio value with current prices."""
        positions = self.get_positions()
        cash = self.get_cash()

        holdings_value = 0
        holdings_detail = []

        for pos in positions:
            ticker = pos['ticker']
            current_price = current_prices.get(ticker, pos['avg_price'])
            market_value = pos['shares'] * current_price
            cost_basis = pos['shares'] * pos['avg_price']
            pnl = market_value - cost_basis
            pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0

            holdings_value += market_value
            holdings_detail.append({
                "ticker": ticker,
                "shares": pos['shares'],
                "avg_price": pos['avg_price'],
                "current_price": current_price,
                "market_value": market_value,
                "cost_basis": cost_basis,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "entry_date": pos['entry_date']
            })

        total_value = cash + holdings_value

        return {
            "cash": cash,
            "holdings_value": holdings_value,
            "total_value": total_value,
            "holdings": holdings_detail
        }

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Calculate performance metrics from trade history."""
        trades = self.get_trade_history(limit=1000)

        if not trades:
            return {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0,
                "total_realized_pnl": 0
            }

        # Group trades by ticker to calculate P&L
        ticker_trades = {}
        for trade in trades:
            ticker = trade['ticker']
            if ticker not in ticker_trades:
                ticker_trades[ticker] = []
            ticker_trades[ticker].append(trade)

        # Calculate realized P&L (simplified: FIFO)
        total_realized_pnl = 0
        wins = 0
        losses = 0

        for ticker, ticker_trade_list in ticker_trades.items():
            buys = [t for t in ticker_trade_list if t['action'] == 'BUY']
            sells = [t for t in ticker_trade_list if t['action'] == 'SELL']

            if buys and sells:
                avg_buy = sum(t['price'] * t['shares']
                              for t in buys) / sum(t['shares'] for t in buys)
                for sell in sells:
                    pnl = (sell['price'] - avg_buy) * sell['shares']
                    total_realized_pnl += pnl
                    if pnl > 0:
                        wins += 1
                    else:
                        losses += 1

        total_closed = wins + losses
        win_rate = (wins / total_closed * 100) if total_closed > 0 else 0

        return {
            "total_trades": len(trades),
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "total_realized_pnl": total_realized_pnl
        }

    # --- RISK MANAGEMENT ---

    def check_stop_loss(self, ticker: str, current_price: float) -> Optional[Dict[str, Any]]:
        """Check if position should be stopped out."""
        position = self.get_position(ticker)
        if not position:
            return None

        stop_loss_pct = st.secrets.get(
            "trading", {}).get("stop_loss_pct", 0.10)
        loss_pct = (position['avg_price'] -
                    current_price) / position['avg_price']

        if loss_pct >= stop_loss_pct:
            return {
                "trigger": "STOP_LOSS",
                "ticker": ticker,
                "entry_price": position['avg_price'],
                "current_price": current_price,
                "loss_pct": loss_pct * 100,
                "shares": position['shares'],
                "action": "SELL"
            }
        return None

    def check_take_profit(self, ticker: str, current_price: float) -> Optional[Dict[str, Any]]:
        """Check if position should take profit."""
        position = self.get_position(ticker)
        if not position:
            return None

        take_profit_pct = st.secrets.get(
            "trading", {}).get("take_profit_pct", 0.20)
        gain_pct = (current_price -
                    position['avg_price']) / position['avg_price']

        if gain_pct >= take_profit_pct:
            return {
                "trigger": "TAKE_PROFIT",
                "ticker": ticker,
                "entry_price": position['avg_price'],
                "current_price": current_price,
                "gain_pct": gain_pct * 100,
                "shares": position['shares'],
                "action": "SELL (50%)"  # Sell half to lock in gains
            }
        return None

    def check_stale_position(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Check if position is stale (held too long without movement)."""
        position = self.get_position(ticker)
        if not position:
            return None

        max_hold_days = st.secrets.get("trading", {}).get("max_hold_days", 30)
        entry_date = datetime.fromisoformat(position['entry_date'])
        days_held = (datetime.now() - entry_date).days

        if days_held >= max_hold_days:
            return {
                "trigger": "STALE",
                "ticker": ticker,
                "days_held": days_held,
                "max_days": max_hold_days,
                "shares": position['shares'],
                "action": "REVIEW"
            }
        return None

    def run_morning_audit(self, current_prices: Dict[str, float]) -> List[Dict[str, Any]]:
        """Run morning audit on all positions. Returns list of alerts."""
        alerts = []
        positions = self.get_positions()

        for pos in positions:
            ticker = pos['ticker']
            current_price = current_prices.get(ticker)

            if not current_price:
                continue

            # Check stop loss
            stop = self.check_stop_loss(ticker, current_price)
            if stop:
                alerts.append(stop)

            # Check take profit
            profit = self.check_take_profit(ticker, current_price)
            if profit:
                alerts.append(profit)

            # Check stale
            stale = self.check_stale_position(ticker)
            if stale:
                alerts.append(stale)

        return alerts

    # --- POSITION SIZING ---

    def calculate_position_size(self, ticker: str, current_price: float,
                                volatility: float = None) -> Dict[str, Any]:
        """Calculate optimal position size based on risk parameters."""
        cash = self.get_cash()
        max_position_pct = st.secrets.get(
            "trading", {}).get("max_position_pct", 0.25)

        # Get current portfolio value
        positions = self.get_positions()
        total_invested = sum(p['shares'] * p['avg_price'] for p in positions)
        portfolio_value = cash + total_invested

        # Max amount for this position
        max_position_value = portfolio_value * max_position_pct

        # Adjust for volatility if provided (higher vol = smaller position)
        if volatility and volatility > 0:
            # Scale down position for high volatility stocks
            # Normalize around 50% vol
            vol_adjustment = min(1.0, 0.5 / volatility)
            max_position_value *= vol_adjustment

        # Can't exceed available cash
        max_position_value = min(max_position_value, cash)

        # Calculate shares
        shares = max_position_value / current_price if current_price > 0 else 0

        return {
            "ticker": ticker,
            "current_price": current_price,
            "max_position_value": max_position_value,
            "recommended_shares": round(shares, 4),
            "cash_available": cash,
            "portfolio_value": portfolio_value
        }

    def sync_with_alpaca(self, alpaca_trader):
        """
        Comprehensive sync with Alpaca:
        1. Account balance → settings + account_history
        2. Positions → positions table (preserving entry dates where possible)
        3. Filled orders → trades table
        4. All orders → order_history table
        """
        if not alpaca_trader.is_connected():
            return False

        try:
            cursor = self.conn.cursor()
            now = datetime.now().isoformat()

            # ============================================
            # 1. SYNC ACCOUNT BALANCE
            # ============================================
            account = alpaca_trader.get_account()
            if account:
                # Update local cash to match Alpaca buying power
                self.update_cash(account['buying_power'])

                # Record account snapshot in history
                cursor.execute("""
                    INSERT INTO account_history (timestamp, cash, buying_power, portfolio_value, equity)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    now,
                    account['cash'],
                    account['buying_power'],
                    account['portfolio_value'],
                    account['equity']
                ))

            # ============================================
            # 2. SYNC POSITIONS (Preserve Entry Dates!)
            # ============================================
            alpaca_positions = alpaca_trader.get_positions()

            # Get existing positions to preserve entry dates
            existing_positions = {p['ticker']: p for p in self.get_positions()}

            # Clear and re-insert (but preserve entry dates)
            cursor.execute("DELETE FROM positions")

            for pos in alpaca_positions:
                ticker = pos['ticker']

                # Try to preserve original entry date if we had this position before
                if ticker in existing_positions:
                    entry_date = existing_positions[ticker]['entry_date']
                else:
                    entry_date = now  # New position, use current time

                cursor.execute("""
                    INSERT INTO positions (ticker, shares, avg_price, entry_date, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    ticker,
                    pos['shares'],
                    pos['avg_price'],
                    entry_date,
                    now
                ))

            # ============================================
            # 3. SYNC TRADES (Using Activities API - More Reliable)
            # ============================================
            # Try activities API first (gives actual fills)
            fills = []
            try:
                if hasattr(alpaca_trader, 'get_all_filled_trades'):
                    fills = alpaca_trader.get_all_filled_trades(limit=500)
            except Exception:
                pass

            if fills:
                for fill in fills:
                    if fill.get('ticker') and fill.get('price', 0) > 0:
                        try:
                            cursor.execute("""
                                INSERT OR IGNORE INTO trades
                                (ticker, action, shares, price, total_value, reason, timestamp, alpaca_order_id)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                fill['ticker'],
                                fill['side'].upper(),
                                fill['qty'],
                                fill['price'],
                                fill['qty'] * fill['price'],
                                "Synced from Alpaca",
                                str(fill['transaction_time']) if fill.get('transaction_time') else now,
                                fill.get('order_id', '')
                            ))
                        except Exception:
                            pass
            else:
                # Fallback to orders API if activities not available
                closed_orders = alpaca_trader.get_orders(status="closed", limit=100)

                for order in closed_orders:
                    status = str(order.get('status', '')).lower()
                    is_filled = 'filled' in status
                    side = str(order.get('side', '')).replace('OrderSide.', '').lower()

                    filled_price = order.get('filled_avg_price', 0) or order.get('price', 0)
                    filled_qty = order.get('filled_qty', 0) or order.get('qty', 0)

                    if is_filled and filled_qty > 0:
                        try:
                            cursor.execute("""
                                INSERT OR IGNORE INTO trades
                                (ticker, action, shares, price, total_value, reason, timestamp, alpaca_order_id)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                order['ticker'],
                                side.upper(),
                                filled_qty,
                                filled_price if filled_price > 0 else 0,
                                filled_qty * filled_price if filled_price > 0 else 0,
                                "Synced from Alpaca",
                                str(order['filled_at']) if order.get('filled_at') else str(order['submitted_at']),
                                order['order_id']
                            ))
                        except Exception:
                            pass

            # ============================================
            # 4. SYNC FULL ORDER HISTORY
            # ============================================
            all_orders = alpaca_trader.get_orders(status="closed", limit=200)

            for order in all_orders:
                cursor.execute("""
                    INSERT OR REPLACE INTO order_history
                    (alpaca_order_id, ticker, side, order_type, qty, filled_qty,
                     filled_avg_price, status, submitted_at, filled_at, synced_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    order['order_id'],
                    order['ticker'],
                    order['side'],
                    order.get('type', 'market'),
                    order['qty'],
                    order.get('filled_qty'),
                    order.get('filled_avg_price'),
                    order['status'],
                    str(order['submitted_at']) if order.get('submitted_at') else None,
                    str(order['filled_at']) if order.get('filled_at') else None,
                    now
                ))

            self.conn.commit()
            return True

        except Exception as e:
            st.error(f"Sync error: {e}")
            return False

    def get_account_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get account balance history."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM account_history ORDER BY timestamp DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def get_order_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get full order history."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM order_history ORDER BY submitted_at DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def close(self):
        """Close database connection."""
        self.conn.close()


# --- STREAMLIT INTEGRATION ---

# @st.cache_resource
def get_portfolio_manager() -> PortfolioManager:
    """Get or create portfolio manager instance."""
    return PortfolioManager()


def render_portfolio_sidebar():
    """Render portfolio information in sidebar."""
    pm = get_portfolio_manager()

    st.sidebar.divider()
    st.sidebar.subheader("Portfolio")

    # Buying Power (stored as "cash" in local DB, synced from Alpaca buying_power)
    buying_power = pm.get_cash()
    st.sidebar.metric("Buying Power", f"${buying_power:,.2f}")

    # Positions
    positions = pm.get_positions()
    if positions:
        st.sidebar.write(f"**Positions ({len(positions)})**")
        for pos in positions:
            st.sidebar.text(
                f"{pos['ticker']}: {pos['shares']:.2f} @ ${pos['avg_price']:.2f}")
    else:
        st.sidebar.caption("No positions")


def render_portfolio_tab(current_prices: Dict[str, float]):
    """Render full portfolio view in main area."""
    pm = get_portfolio_manager()

    st.header("Portfolio Overview")

    # Get portfolio value
    portfolio = pm.get_portfolio_value(current_prices)

    # Top metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Cash", f"${portfolio['cash']:.2f}")
    with col2:
        st.metric("Holdings", f"${portfolio['holdings_value']:.2f}")
    with col3:
        st.metric("Total Value", f"${portfolio['total_value']:.2f}")

    # --- PORTFOLIO CHART (REAL DATA ONLY) ---
    try:
        from utils.alpaca import get_alpaca_trader
        import plotly.graph_objects as go

        trader = get_alpaca_trader()
        if trader.is_connected():
            # Create a collapsible chart
            with st.expander("📈 Portfolio Performance", expanded=True):

                # 1. Try to fetch Monthly History (Daily Candles)
                history_df = trader.get_portfolio_history(
                    period="1M", timeframe="1D")
                chart_title = "Equity Curve (30 Days)"

                # 2. If empty (New Account), fetch Intraday History (Minute Candles)
                if history_df is None or history_df.empty:
                    history_df = trader.get_portfolio_history(
                        period="1D", timeframe="1Min")
                    chart_title = "Equity Curve (Today - Real Time)"

                if history_df is not None and not history_df.empty:
                    fig = go.Figure()

                    # Color logic
                    start_eq = history_df['equity'].iloc[0]
                    end_eq = history_df['equity'].iloc[-1]

                    if end_eq >= start_eq:
                        line_color = '#00C805'  # Green
                        fill_color = 'rgba(0, 200, 5, 0.2)'
                    else:
                        line_color = '#FF5000'  # Red
                        fill_color = 'rgba(255, 80, 0, 0.2)'

                    fig.add_trace(go.Scatter(
                        x=history_df.index,
                        y=history_df['equity'],
                        mode='lines',
                        line=dict(color=line_color, width=2),
                        fill='tozeroy',
                        fillcolor=fill_color,
                        name='Equity'
                    ))

                    # Dynamic Range
                    y_min = history_df['equity'].min() * 0.999  # Zoom in tight
                    y_max = history_df['equity'].max() * 1.001

                    fig.update_layout(
                        height=350,
                        template="plotly_dark",
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        margin=dict(l=10, r=10, t=30, b=10),
                        hovermode="x unified",
                        xaxis=dict(
                            showgrid=False,
                            showspikes=True,
                            spikethickness=1,
                            spikedash='dot',
                            spikecolor='#999999',
                            spikemode='across'
                        ),
                        yaxis=dict(
                            showgrid=True,
                            gridcolor='rgba(255,255,255,0.1)',
                            side="right",
                            tickprefix="$",
                            range=[y_min, y_max],
                            showspikes=True
                        ),
                        showlegend=False,
                        title=chart_title
                    )

                    st.plotly_chart(fig, width='stretch')
                else:
                    st.info(
                        "Waiting for market data... (Chart populates after first trade clears)")
    except Exception as e:
        # st.error(f"Chart error: {e}")
        st.caption("Chart unavailable (Check API connection)")

    st.divider()

    # Holdings table
    if portfolio['holdings']:
        st.subheader("Current Holdings")

        df = pd.DataFrame(portfolio['holdings'])
        df['pnl_display'] = df.apply(
            lambda x: f"${x['pnl']:.2f} ({x['pnl_pct']:+.1f}%)", axis=1
        )

        # Color code P&L
        st.dataframe(
            df[['ticker', 'shares', 'avg_price',
                'current_price', 'market_value', 'pnl_display']],
            column_config={
                "ticker": "Ticker",
                "shares": st.column_config.NumberColumn("Shares", format="%.2f"),
                "avg_price": st.column_config.NumberColumn("Avg Price", format="$%.2f"),
                "current_price": st.column_config.NumberColumn("Current", format="$%.2f"),
                "market_value": st.column_config.NumberColumn("Value", format="$%.2f"),
                "pnl_display": "P&L"
            },
            hide_index=True,
            width='stretch'
        )
    else:
        st.info("No positions. Use the Scanner to find opportunities!")

    # Morning Audit Alerts
    alerts = pm.run_morning_audit(current_prices)
    if alerts:
        st.divider()
        st.subheader("Alerts")
        for alert in alerts:
            if alert['trigger'] == 'STOP_LOSS':
                st.error(
                    f"STOP LOSS: {alert['ticker']} is down {alert['loss_pct']:.1f}% - Consider selling")
            elif alert['trigger'] == 'TAKE_PROFIT':
                st.success(
                    f"TAKE PROFIT: {alert['ticker']} is up {alert['gain_pct']:.1f}% - Consider taking profits")
            elif alert['trigger'] == 'STALE':
                st.warning(
                    f"STALE: {alert['ticker']} held for {alert['days_held']} days - Review position")

    # Trade History
    st.divider()
    st.subheader("Recent Trades")
    trades = pm.get_trade_history(limit=10)

    if trades:
        trades_df = pd.DataFrame(trades)
        trades_df['timestamp'] = pd.to_datetime(
            trades_df['timestamp']).dt.strftime('%Y-%m-%d %H:%M')

        st.dataframe(
            trades_df[['timestamp', 'ticker', 'action',
                       'shares', 'price', 'total_value', 'reason']],
            column_config={
                "timestamp": "Date",
                "ticker": "Ticker",
                "action": "Action",
                "shares": st.column_config.NumberColumn("Shares", format="%.2f"),
                "price": st.column_config.NumberColumn("Price", format="$%.2f"),
                "total_value": st.column_config.NumberColumn("Total", format="$%.2f"),
                "reason": "Reason"
            },
            hide_index=True,
            width='stretch'
        )
    else:
        st.caption("No trades yet")

    # Performance Metrics
    st.divider()
    metrics = pm.get_performance_metrics()
    st.subheader("Performance")

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total Trades", metrics['total_trades'])
    with m2:
        st.metric("Win Rate", f"{metrics['win_rate']:.1f}%")
    with m3:
        st.metric("Wins/Losses", f"{metrics['wins']}/{metrics['losses']}")
    with m4:
        pnl_color = "normal" if metrics['total_realized_pnl'] >= 0 else "inverse"
        st.metric("Realized P&L", f"${metrics['total_realized_pnl']:.2f}",
                  delta_color=pnl_color)
