"""
Alpaca Paper Trading Integration (using alpaca-py SDK)
The "Executor" of Silicon Oracle
"""

import streamlit as st
from typing import Dict, Any, Optional, List
from datetime import datetime
import pandas as pd


class AlpacaTrader:
    """Wrapper for Alpaca Paper Trading API using alpaca-py SDK."""

    def __init__(self):
        self.trading_client = None
        self._initialize()

    def _initialize(self):
        """Initialize Alpaca API connection."""
        try:
            from alpaca.trading.client import TradingClient

            # AUTO-FIX: Use BYOK keys if available
            from utils.auth import get_user_decrypted_keys, is_logged_in

            api_key = None
            secret_key = None

            if is_logged_in():
                user_keys = get_user_decrypted_keys()
                api_key = user_keys.get("alpaca_api_key")
                secret_key = user_keys.get("alpaca_secret_key")

            # Fallback to secrets only if NO user keys found (e.g. local admin or dev mode)
            if not api_key:
                api_key = st.secrets.get("alpaca", {}).get("api_key")
                secret_key = st.secrets.get("alpaca", {}).get("secret_key")

            if not api_key or not secret_key:
                # No keys available at all
                self.trading_client = None
                return

            # Paper trading is determined by the API keys
            self.trading_client = TradingClient(
                api_key=api_key,
                secret_key=secret_key,
                paper=True
            )
        except Exception as e:
            st.error(f"Failed to connect to Alpaca: {e}")
            self.trading_client = None

    def is_connected(self) -> bool:
        return self.trading_client is not None

    # --- ACCOUNT INFO ---

    def get_account(self) -> Optional[Dict[str, Any]]:
        if not self.trading_client:
            return None
        try:
            account = self.trading_client.get_account()
            return {
                "buying_power": float(account.buying_power),
                "portfolio_value": float(account.portfolio_value),
                "cash": float(account.cash),
                "equity": float(account.equity)
            }
        except Exception as e:
            st.error(f"Error getting account: {e}")
            return None

    def get_portfolio_history(self, period: str = "1M", timeframe: str = "1D") -> Optional[pd.DataFrame]:
        """
        Get portfolio equity history.
        FIXED: Removed broken PortfolioTimeFrame import. Uses raw strings.
        """
        if not self.trading_client:
            return None

        try:
            from alpaca.trading.requests import GetPortfolioHistoryRequest

            # Map user friendly timeframe to API strings
            tf_map = {
                "1Min": "1Min",
                "5Min": "5Min",
                "15Min": "15Min",
                "1H": "1H",
                "1D": "1D"
            }

            # Use raw strings instead of the broken Enum
            api_timeframe = tf_map.get(timeframe, "1D")

            req = GetPortfolioHistoryRequest(
                period=period,
                timeframe=api_timeframe,
                extended_hours=True
            )

            history = self.trading_client.get_portfolio_history(req)

            # Convert to DataFrame
            df = pd.DataFrame({
                "timestamp": history.timestamp,
                "equity": history.equity,
                "profit_loss": history.profit_loss,
                "profit_loss_pct": history.profit_loss_pct
            })

            # Clean timestamps - keep as column for chart compatibility
            df['timestamp'] = pd.to_datetime(
                df['timestamp'], unit='s', utc=True)
            df['timestamp'] = df['timestamp'].dt.tz_convert('America/New_York')

            # Filter out zero-equity rows (account had no funds)
            df = df[df['equity'] > 0]

            return df if not df.empty else None

        except Exception as e:
            # Silence validation errors for new accounts
            if "validation error" not in str(e).lower():
                pass
            return None

    # --- POSITIONS ---

    def get_positions(self) -> List[Dict[str, Any]]:
        if not self.trading_client:
            return []
        try:
            positions = self.trading_client.get_all_positions()
            return [{
                "ticker": pos.symbol,
                "shares": float(pos.qty),
                "avg_price": float(pos.avg_entry_price),
                "current_price": float(pos.current_price),
                "market_value": float(pos.market_value),
                "unrealized_pl": float(pos.unrealized_pl),
                "unrealized_plpc": float(pos.unrealized_plpc) * 100
            } for pos in positions]
        except:
            return []

    def get_position(self, ticker: str) -> Optional[Dict[str, Any]]:
        if not self.trading_client:
            return None
        try:
            pos = self.trading_client.get_open_position(ticker.upper())
            return {
                "ticker": pos.symbol,
                "shares": float(pos.qty),
                "avg_price": float(pos.avg_entry_price),
                "unrealized_pl": float(pos.unrealized_pl),
                "shares": float(pos.qty)  # Added explicit shares key
            }
        except:
            return None

    # --- ORDERS ---

    def submit_order(self, ticker: str, qty: float, side: str, order_type: str = "market", limit_price: float = None) -> Dict[str, Any]:
        if not self.trading_client:
            return {"success": False, "error": "API Error"}

        try:
            from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce

            ticker = ticker.upper()
            side_enum = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL

            if order_type.lower() == "market":
                req = MarketOrderRequest(
                    symbol=ticker, qty=qty, side=side_enum, time_in_force=TimeInForce.DAY)
            else:
                req = LimitOrderRequest(symbol=ticker, qty=qty, side=side_enum,
                                        time_in_force=TimeInForce.DAY, limit_price=limit_price)

            order = self.trading_client.submit_order(req)
            return {"success": True, "order_id": str(order.id)}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def buy(self, ticker, qty, order_type="market", limit_price=None):
        return self.submit_order(ticker, qty, "buy", order_type, limit_price)

    def sell(self, ticker, qty, order_type="market", limit_price=None):
        return self.submit_order(ticker, qty, "sell", order_type, limit_price)

    def cancel_order(self, order_id: str):
        try:
            self.trading_client.cancel_order_by_id(order_id)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_orders(self, status="open", limit=10):
        if not self.trading_client:
            return []
        try:
            from alpaca.trading.requests import GetOrdersRequest
            from alpaca.trading.enums import QueryOrderStatus

            q_status = QueryOrderStatus.OPEN if status == "open" else QueryOrderStatus.CLOSED
            req = GetOrdersRequest(status=q_status, limit=limit)
            orders = self.trading_client.get_orders(req)

            return [{
                "order_id": str(o.id),
                "ticker": o.symbol,
                # 'buy' or 'sell'
                "side": str(o.side).replace("OrderSide.", "").lower(),
                "qty": float(o.qty or 0),
                "filled_qty": float(o.filled_qty or 0),
                # 'filled', 'canceled', etc.
                "status": str(o.status).replace("OrderStatus.", "").lower(),
                "type": str(o.type).replace("OrderType.", "").lower(),
                "submitted_at": o.submitted_at,
                "filled_at": o.filled_at,  # When order was actually executed
                "filled_avg_price": float(o.filled_avg_price or 0)
            } for o in orders]
        except:
            return []

    def is_market_open(self) -> bool:
        """Check if market is currently open."""
        if not self.trading_client:
            return False
        try:
            clock = self.trading_client.get_clock()
            return clock.is_open
        except:
            return False

    def get_activities(self, activity_type: str = "FILL", limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get account activities (trades, dividends, etc.).
        activity_type: FILL, DIV, ACATC, ACATS, CSD, CSW, etc.
        """
        if not self.trading_client:
            return []
        try:
            from alpaca.trading.requests import GetAccountActivitiesRequest
            from alpaca.trading.enums import ActivityType

            # Map string to enum
            type_map = {
                "FILL": ActivityType.FILL,
                "DIV": ActivityType.DIV,
                "ACATC": ActivityType.ACATC,  # ACATS cash
                "ACATS": ActivityType.ACATS,  # ACATS securities
                "CSD": ActivityType.CSD,      # Cash disbursement
                "CSW": ActivityType.CSW,      # Cash withdrawal
            }

            act_type = type_map.get(activity_type.upper(), ActivityType.FILL)
            req = GetAccountActivitiesRequest(activity_types=[act_type])
            activities = self.trading_client.get_account_activities(req)

            results = []
            for a in activities[:limit]:
                # FILL activities have different fields than other types
                if activity_type.upper() == "FILL":
                    results.append({
                        "id": str(a.id),
                        "activity_type": str(a.activity_type),
                        "ticker": getattr(a, 'symbol', None),
                        "side": str(getattr(a, 'side', '')).replace("OrderSide.", "").lower(),
                        "qty": float(getattr(a, 'qty', 0) or 0),
                        "price": float(getattr(a, 'price', 0) or 0),
                        "transaction_time": getattr(a, 'transaction_time', None),
                        "order_id": str(getattr(a, 'order_id', '')),
                        "cumulative_qty": float(getattr(a, 'cum_qty', 0) or 0),
                        "leaves_qty": float(getattr(a, 'leaves_qty', 0) or 0),
                    })
                else:
                    # Non-fill activities (dividends, transfers)
                    results.append({
                        "id": str(a.id),
                        "activity_type": str(a.activity_type),
                        "date": getattr(a, 'date', None),
                        "net_amount": float(getattr(a, 'net_amount', 0) or 0),
                        "description": getattr(a, 'description', ''),
                    })
            return results
        except Exception as e:
            return []

    def get_all_filled_trades(self, limit: int = 500) -> List[Dict[str, Any]]:
        """Get all filled trades using activities API (more reliable than orders)."""
        return self.get_activities(activity_type="FILL", limit=limit)

    def get_news(self, ticker: str, limit: int = 10) -> List[Any]:
        """Fetch news for ticker using Alpaca News API."""
        if not self.trading_client:
            return []
        try:
            from alpaca.data.historical import NewsClient
            from alpaca.data.requests import NewsRequest
            from datetime import datetime, timedelta

            # Re-use API keys
            api_key = st.secrets["alpaca"]["api_key"]
            secret_key = st.secrets["alpaca"]["secret_key"]

            # News uses a separate client
            news_client = NewsClient(api_key=api_key, secret_key=secret_key)

            # Create request for news from past 7 days
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)

            req = NewsRequest(
                symbols=ticker,
                start=start_date,
                end=end_date,
                limit=limit,
                sort="desc"  # Most recent first
            )

            news_set = news_client.get_news(req)

            # news_set is a dict with ticker keys
            if ticker.upper() in news_set:
                return news_set[ticker.upper()]
            elif hasattr(news_set, 'news'):
                return news_set.news
            else:
                # Try to get news list from response
                news_list = list(news_set.values())[0] if news_set else []
                return news_list

        except Exception as e:
            # News API might not be available on free tier
            # st.warning(f"Alpaca News Error: {e}")
            return []

    # --- WATCHLISTS ---

    def get_watchlists(self) -> List[Dict[str, Any]]:
        """Get all watchlists from Alpaca."""
        if not self.trading_client:
            return []
        try:
            watchlists = self.trading_client.get_watchlists()
            return [{
                "id": str(wl.id),
                "name": wl.name,
                "account_id": str(wl.account_id),
                "assets": [asset.symbol for asset in (wl.assets or [])],
                "created_at": str(wl.created_at),
                "updated_at": str(wl.updated_at)
            } for wl in watchlists]
        except Exception as e:
            return []

    def get_watchlist(self, watchlist_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific watchlist by ID."""
        if not self.trading_client:
            return None
        try:
            wl = self.trading_client.get_watchlist_by_id(watchlist_id)
            return {
                "id": str(wl.id),
                "name": wl.name,
                "assets": [asset.symbol for asset in (wl.assets or [])],
                "created_at": str(wl.created_at)
            }
        except Exception:
            return None

    def create_watchlist(self, name: str, symbols: List[str] = None) -> Optional[Dict[str, Any]]:
        """Create a new watchlist."""
        if not self.trading_client:
            return None
        try:
            from alpaca.trading.requests import CreateWatchlistRequest

            req = CreateWatchlistRequest(
                name=name,
                symbols=symbols or []
            )
            wl = self.trading_client.create_watchlist(req)
            return {
                "id": str(wl.id),
                "name": wl.name,
                "assets": [asset.symbol for asset in (wl.assets or [])]
            }
        except Exception as e:
            return None

    def add_to_watchlist(self, watchlist_id: str, symbol: str) -> bool:
        """Add a symbol to an existing watchlist."""
        if not self.trading_client:
            return False
        try:
            self.trading_client.add_asset_to_watchlist_by_id(
                watchlist_id=watchlist_id,
                symbol=symbol.upper()
            )
            return True
        except Exception:
            return False

    def remove_from_watchlist(self, watchlist_id: str, symbol: str) -> bool:
        """Remove a symbol from a watchlist."""
        if not self.trading_client:
            return False
        try:
            self.trading_client.remove_asset_from_watchlist_by_id(
                watchlist_id=watchlist_id,
                symbol=symbol.upper()
            )
            return True
        except Exception:
            return False

    def delete_watchlist(self, watchlist_id: str) -> bool:
        """Delete a watchlist."""
        if not self.trading_client:
            return False
        try:
            self.trading_client.delete_watchlist_by_id(watchlist_id)
            return True
        except Exception:
            return False


# --- STREAMLIT INTEGRATION ---


@st.cache_resource
def get_alpaca_trader() -> AlpacaTrader:
    """Get or create Alpaca trader instance."""
    return AlpacaTrader()


def render_alpaca_account():
    """Render Alpaca account info in sidebar."""
    trader = get_alpaca_trader()

    if not trader.is_connected():
        st.sidebar.warning("Alpaca not connected")
        return

    account = trader.get_account()
    if not account:
        return

    st.sidebar.divider()
    st.sidebar.subheader("Paper Trading")

    # Market status
    market_open = trader.is_market_open()
    status_icon = "🟢" if market_open else "🔴"
    st.sidebar.caption(
        f"{status_icon} Market {'Open' if market_open else 'Closed'}")

    # Account metrics
    st.sidebar.metric("Buying Power", f"${account['buying_power']:,.2f}")
    st.sidebar.metric("Portfolio Value", f"${account['portfolio_value']:,.2f}")


def render_trade_dialog(ticker: str, current_price: float, signal: str):
    """Render trade execution dialog."""
    trader = get_alpaca_trader()

    if not trader.is_connected():
        st.error("Alpaca not connected. Check your API keys.")
        return

    account = trader.get_account()
    if not account:
        return

    st.subheader(f"Execute Trade: {ticker}")

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Current Price", f"${current_price:.2f}")
        st.metric("Buying Power", f"${account['buying_power']:,.2f}")

    with col2:
        # Check existing position
        position = trader.get_position(ticker)
        if position:
            st.metric("Current Position", f"{position['shares']:.2f} shares")
            st.metric("Unrealized P&L", f"${position['unrealized_pl']:.2f}")

    st.divider()

    # Order form
    col1, col2 = st.columns(2)

    with col1:
        side = st.radio("Action", ["BUY", "SELL"],
                        horizontal=True, key=f"side_{ticker}")

    with col2:
        order_type = st.radio(
            "Order Type", ["Market", "Limit"], horizontal=True, key=f"type_{ticker}")

    # Quantity
    max_shares = account['buying_power'] / current_price if side == "BUY" else (
        position['shares'] if position else 0
    )

    # Handle case where max_shares is 0 (e.g. no cash or no position)
    max_val = float(max_shares) if max_shares > 0 else 0.0

    qty = st.number_input(
        "Shares",
        min_value=0.0,
        max_value=max_val if max_val > 0 else 1000000.0,  # Avoid max_value=0 error
        value=min(1.0, max_val) if max_val > 0 else 0.0,
        step=0.1,
        key=f"qty_{ticker}"
    )

    # Limit price (if limit order)
    limit_price = None
    if order_type == "Limit":
        limit_price = st.number_input(
            "Limit Price",
            min_value=0.01,
            value=current_price,
            step=0.01,
            key=f"limit_{ticker}"
        )

    # Order preview
    total = qty * (limit_price if limit_price else current_price)
    st.info(f"Order Total: ${total:.2f}")

    # Safety confirmation
    st.warning("This is PAPER TRADING - no real money involved!")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Execute Order", type="primary", width='stretch', key=f"exec_{ticker}"):
            with st.spinner("Submitting order..."):
                if side == "BUY":
                    result = trader.buy(
                        ticker, qty, order_type.lower(), limit_price)
                else:
                    result = trader.sell(
                        ticker, qty, order_type.lower(), limit_price)

                if result['success']:
                    st.success(f"Order submitted! ID: {result['order_id']}")
                    st.balloons()
                else:
                    st.error(f"Order failed: {result['error']}")

    with col2:
        if st.button("Cancel", width='stretch', key=f"cancel_{ticker}"):
            st.rerun()


def render_orders_tab():
    """Render orders management tab."""
    trader = get_alpaca_trader()

    if not trader.is_connected():
        st.error("Alpaca not connected")
        return

    st.header("Orders & Activity")

    # Open orders
    st.subheader("Open Orders")
    open_orders = trader.get_orders(status="open")

    if open_orders:
        for order in open_orders:
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            with col1:
                st.write(
                    f"**{order['ticker']}** - {order['side'].upper()} {order['qty']} shares")
            with col2:
                st.write(f"Type: {order['type']}")
            with col3:
                st.write(f"Status: {order['status']}")
            with col4:
                if st.button("Cancel", key=f"cancel_{order['order_id']}"):
                    result = trader.cancel_order(order['order_id'])
                    if result['success']:
                        st.success("Order cancelled")
                        st.rerun()
                    else:
                        st.error(result['error'])
    else:
        st.caption("No open orders")

    st.divider()

    # Recent closed orders
    st.subheader("Recent Orders")
    closed_orders = trader.get_orders(status="closed", limit=10)

    if closed_orders:
        import pandas as pd
        df = pd.DataFrame(closed_orders)

        # Check columns existence to avoid KeyError
        cols = ['ticker', 'side', 'qty', 'status', 'submitted_at']
        # filled_avg_price might be missing depending on how we constructed the dict
        # In my manual code I think I included it? Let's check my rewrite logic above.
        # Yes, I included it.

        st.dataframe(
            df,
            hide_index=True,
            width='stretch'
        )
    else:
        st.caption("No recent orders")

    # Positions from Alpaca
    st.divider()
    st.subheader("Alpaca Positions")
    positions = trader.get_positions()

    if positions:
        import pandas as pd
        df = pd.DataFrame(positions)
        st.dataframe(
            df[['ticker', 'shares', 'avg_price', 'current_price',
                'unrealized_pl', 'unrealized_plpc']],
            column_config={
                "ticker": "Ticker",
                "shares": st.column_config.NumberColumn("Shares", format="%.2f"),
                "avg_price": st.column_config.NumberColumn("Avg Price", format="$%.2f"),
                "current_price": st.column_config.NumberColumn("Current", format="$%.2f"),
                "unrealized_pl": st.column_config.NumberColumn("P&L", format="$%.2f"),
                "unrealized_plpc": st.column_config.NumberColumn("P&L %", format="%.2f%%")
            },
            hide_index=True,
            width='stretch'
        )
    else:
        st.caption("No positions")


def render_alpaca_account():
    """Render Alpaca account info in sidebar."""
    trader = get_alpaca_trader()

    if not trader.is_connected():
        st.sidebar.warning("Alpaca not connected")
        return

    account = trader.get_account()
    if not account:
        return

    st.sidebar.divider()
    st.sidebar.subheader("Paper Trading")

    # Market status
    market_open = trader.is_market_open()
    status_icon = "🟢" if market_open else "🔴"
    st.sidebar.caption(
        f"{status_icon} Market {'Open' if market_open else 'Closed'}")

    # Account metrics
    st.sidebar.metric("Buying Power", f"${account['buying_power']:,.2f}")
    st.sidebar.metric("Portfolio Value", f"${account['portfolio_value']:,.2f}")


def render_trade_dialog(ticker: str, current_price: float, signal: str):
    """Render trade execution dialog."""
    trader = get_alpaca_trader()

    if not trader.is_connected():
        st.error("Alpaca not connected. Check your API keys.")
        return

    account = trader.get_account()
    if not account:
        return

    st.subheader(f"Execute Trade: {ticker}")

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Current Price", f"${current_price:.2f}")
        st.metric("Buying Power", f"${account['buying_power']:,.2f}")

    with col2:
        # Check existing position
        position = trader.get_position(ticker)
        if position:
            st.metric("Current Position", f"{position['shares']:.2f} shares")
            st.metric("Unrealized P&L", f"${position['unrealized_pl']:.2f}")

    st.divider()

    # Order form
    col1, col2 = st.columns(2)

    with col1:
        side = st.radio("Action", ["BUY", "SELL"],
                        horizontal=True, key=f"side_{ticker}")

    with col2:
        order_type = st.radio(
            "Order Type", ["Market", "Limit"], horizontal=True, key=f"type_{ticker}")

    # Quantity
    max_shares = account['buying_power'] / current_price if side == "BUY" else (
        position['shares'] if position else 0
    )

    qty = st.number_input(
        "Shares",
        min_value=0.0,
        max_value=float(max_shares),
        value=min(1.0, max_shares) if max_shares > 0 else 0.0,
        step=0.1,
        key=f"qty_{ticker}"
    )

    # Limit price (if limit order)
    limit_price = None
    if order_type == "Limit":
        limit_price = st.number_input(
            "Limit Price",
            min_value=0.01,
            value=current_price,
            step=0.01,
            key=f"limit_{ticker}"
        )

    # Order preview
    total = qty * (limit_price if limit_price else current_price)
    st.info(f"Order Total: ${total:.2f}")

    # Safety confirmation
    st.warning("This is PAPER TRADING - no real money involved!")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Execute Order", type="primary", width='stretch', key=f"exec_{ticker}"):
            with st.spinner("Submitting order..."):
                if side == "BUY":
                    result = trader.buy(
                        ticker, qty, order_type.lower(), limit_price)
                else:
                    result = trader.sell(
                        ticker, qty, order_type.lower(), limit_price)

                if result['success']:
                    st.success(f"Order submitted! ID: {result['order_id']}")
                    st.balloons()
                else:
                    st.error(f"Order failed: {result['error']}")

    with col2:
        if st.button("Cancel", width='stretch', key=f"cancel_{ticker}"):
            st.rerun()


def render_orders_tab():
    """Render orders management tab."""
    trader = get_alpaca_trader()

    if not trader.is_connected():
        st.error("Alpaca not connected")
        return

    st.header("Orders & Activity")

    # Open orders
    st.subheader("Open Orders")
    open_orders = trader.get_orders(status="open")

    if open_orders:
        for order in open_orders:
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            with col1:
                st.write(
                    f"**{order['ticker']}** - {order['side'].upper()} {order['qty']} shares")
            with col2:
                st.write(f"Type: {order['type']}")
            with col3:
                st.write(f"Status: {order['status']}")
            with col4:
                if st.button("Cancel", key=f"cancel_{order['order_id']}"):
                    result = trader.cancel_order(order['order_id'])
                    if result['success']:
                        st.success("Order cancelled")
                        st.rerun()
                    else:
                        st.error(result['error'])
    else:
        st.caption("No open orders")

    st.divider()

    # Recent closed orders
    st.subheader("Recent Orders")
    closed_orders = trader.get_orders(status="closed", limit=20)

    if closed_orders:
        import pandas as pd
        df = pd.DataFrame(closed_orders)

        # Format timestamps
        if 'filled_at' in df.columns:
            df['filled_at'] = pd.to_datetime(
                df['filled_at']).dt.strftime('%m/%d %H:%M')
        if 'submitted_at' in df.columns:
            df['submitted_at'] = pd.to_datetime(
                df['submitted_at']).dt.strftime('%m/%d %H:%M')

        # Format side for display (capitalize)
        if 'side' in df.columns:
            df['side'] = df['side'].str.upper()

        # Safe access to fields
        display_cols = ['ticker', 'side', 'filled_qty',
                        'filled_avg_price', 'status', 'filled_at']
        display_cols = [c for c in display_cols if c in df.columns]

        if display_cols:
            st.dataframe(
                df[display_cols],
                column_config={
                    "ticker": "Ticker",
                    "side": "Side",
                    "filled_qty": st.column_config.NumberColumn("Filled Qty", format="%.4f"),
                    "filled_avg_price": st.column_config.NumberColumn("Avg Price", format="$%.2f"),
                    "status": "Status",
                    "filled_at": "Filled At"
                },
                hide_index=True,
                width='stretch'
            )
        else:
            st.write(df)  # Fallback view
    else:
        st.caption("No recent orders")

    # Positions from Alpaca
    st.divider()
    st.subheader("Alpaca Positions")
    positions = trader.get_positions()

    if positions:
        import pandas as pd
        df = pd.DataFrame(positions)
        st.dataframe(
            df[['ticker', 'shares', 'avg_price', 'current_price',
                'unrealized_pl', 'unrealized_plpc']],
            column_config={
                "ticker": "Ticker",
                "shares": st.column_config.NumberColumn("Shares", format="%.2f"),
                "avg_price": st.column_config.NumberColumn("Avg Price", format="$%.2f"),
                "current_price": st.column_config.NumberColumn("Current", format="$%.2f"),
                "unrealized_pl": st.column_config.NumberColumn("P&L", format="$%.2f"),
                "unrealized_plpc": st.column_config.NumberColumn("P&L %", format="%.2f%%")
            },
            hide_index=True,
            width='stretch'
        )
    else:
        st.caption("No positions")


@st.cache_resource
def get_alpaca_trader_instance(user_id_stub=None):
    """
    Get AlpacaTrader instance.
    The user_id_stub argument is effectively ignored by the function body
    but used by streamlit's cache system to force a unique instance per user.
    """
    return AlpacaTrader()


def get_alpaca_trader():
    """Get the current user's AlpacaTrader instance."""
    from utils.auth import get_current_user_id
    user_id = get_current_user_id()
    # Pass user_id to cache function so we get a unique instance per user
    return get_alpaca_trader_instance(user_id)
