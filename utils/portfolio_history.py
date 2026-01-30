import pandas as pd
import streamlit as st
from utils.alpaca import get_alpaca_trader


@st.cache_data(ttl=60)  # Cache for 1 min
def get_portfolio_history(period="1M", timeframe="1D"):
    """
    Fetches historical portfolio equity from Alpaca.
    Delegates to the robust AlpacaTrader implementation.
    """
    trader = get_alpaca_trader()
    if not trader:
        return None

    return trader.get_portfolio_history(period=period, timeframe=timeframe)
