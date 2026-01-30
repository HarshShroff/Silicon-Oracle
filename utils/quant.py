import numpy as np
import pandas as pd
import yfinance as yf
import streamlit as st
from datetime import datetime, timedelta


@st.cache_data(ttl=3600)
def calculate_optimal_position(ticker, portfolio_value, risk_tolerance="Moderate"):
    """
    Calculates optimal position size using Volatility Targeting & Kelly Criterion.
    Strategy: Try yfinance first (Rich Data), failover to Alpaca (Reliable Data).
    """
    hist = None

    # --- METHOD 1: YFINANCE (Primary) ---
    # --- METHOD 1: YFINANCE (Primary) ---
    try:
        import logging
        import requests
        logging.getLogger('yfinance').setLevel(logging.CRITICAL)

        # CRITICAL FIX: Use clean session with User-Agent
        clean_session = requests.Session()
        clean_session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        stock = yf.Ticker(ticker, session=clean_session)
        hist = stock.history(period="1y")

        # Check if empty (common yfinance failure mode)
        if hist is None or hist.empty:
            raise ValueError("yfinance returned empty data")

    except Exception as e:
        # --- METHOD 2: ALPACA BACKUP (Failover) ---
        # print(f"Quant: yfinance failed ({e}), trying Alpaca...")
        try:
            from utils.alpaca import get_alpaca_trader
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame

            # Get the client from your existing utils
            trader = get_alpaca_trader()

            # Use the historical data client
            # We need to construct the request manually
            if trader.is_connected():
                # We need a dedicated data client for history,
                # but we can try to use the raw request if possible or re-init
                from alpaca.data.historical import StockHistoricalDataClient

                api_key = st.secrets["alpaca"]["api_key"]
                secret_key = st.secrets["alpaca"]["secret_key"]

                data_client = StockHistoricalDataClient(api_key, secret_key)

                # Fetch last 252 trading days (approx 1 year)
                req = StockBarsRequest(
                    symbol_or_symbols=ticker,
                    timeframe=TimeFrame.Day,
                    start=datetime.now() - timedelta(days=365),
                    limit=252
                )

                bars = data_client.get_stock_bars(req)

                # Convert to DataFrame matching yfinance structure
                if not bars.df.empty:
                    hist = bars.df
                    # Alpaca returns multi-index, flatten it
                    if isinstance(hist.index, pd.MultiIndex):
                        hist = hist.reset_index(level=0, drop=True)

                    # Rename columns to match yfinance (close -> Close)
                    hist.rename(columns={'close': 'Close'}, inplace=True)
        except Exception as alpaca_error:
            st.error(f"❌ Data Fetch Failed: {alpaca_error}")
            return None

    # Final Check
    if hist is None or hist.empty:
        return None

    # --- THE MATH (Same as before) ---
    try:
        # Calculate Returns
        hist['Daily_Return'] = hist['Close'].pct_change()
        daily_volatility = hist['Daily_Return'].std()

        # Annualize (252 trading days)
        annual_volatility = daily_volatility * np.sqrt(252)
        current_price = hist['Close'].iloc[-1]

        # Risk Factors
        if risk_tolerance == "Conservative":
            target_vol_impact = 0.01
            kelly_fraction = 0.25
        elif risk_tolerance == "Aggressive":
            target_vol_impact = 0.05
            kelly_fraction = 1.0
        else:  # Moderate
            target_vol_impact = 0.02
            kelly_fraction = 0.5

        # 1. Volatility Sizing
        if annual_volatility > 0:
            vol_position_value = (
                portfolio_value * target_vol_impact) / annual_volatility
        else:
            vol_position_value = 0

        # Cap at 20% portfolio
        vol_position_value = min(vol_position_value, portfolio_value * 0.20)
        vol_shares = int(vol_position_value /
                         current_price) if current_price > 0 else 0

        # 2. Kelly Criterion
        wins = hist[hist['Daily_Return'] > 0]
        losses = hist[hist['Daily_Return'] < 0]

        win_rate = len(wins) / len(hist) if len(hist) > 0 else 0
        avg_win = wins['Daily_Return'].mean() if not wins.empty else 0
        avg_loss = abs(losses['Daily_Return'].mean()
                       ) if not losses.empty else 0

        if avg_loss > 0:
            win_loss_ratio = avg_win / avg_loss
            kelly_pct = win_rate - ((1 - win_rate) / win_loss_ratio)
        else:
            kelly_pct = 0

        # Safety Capping
        safe_kelly = max(0, min(kelly_pct * kelly_fraction, 0.25))

        kelly_position_value = portfolio_value * safe_kelly
        kelly_shares = int(kelly_position_value /
                           current_price) if current_price > 0 else 0

        return {
            "current_price": current_price,
            "annual_volatility": annual_volatility * 100,
            "vol_sizing": {
                "shares": vol_shares,
                "value": vol_shares * current_price,
                "method": "Volatility Target"
            },
            "kelly_sizing": {
                "shares": kelly_shares,
                "value": kelly_shares * current_price,
                "method": f"Kelly Criterion ({risk_tolerance})"
            }
        }

    except Exception as e:
        st.error(f"Quant Math Error: {e}")
        return None
