import yfinance as yf
import pandas as pd
import pandas_ta_classic as ta  # The Technical Analysis library
import plotly.graph_objects as go
from datetime import datetime, timedelta

# 1. The Setup
print("--- THE SILICON ORACLE (Phase 1) ---")
ticker = input("Enter Stock Ticker (e.g., NVDA, MSFT): ").upper()

# 2. Get Data (2 Years)
# We use '1d' interval (Daily candles) suitable for Swing Trading
end_date = datetime.now()
start_date = end_date - timedelta(days=730)

print(f"Fetching data for {ticker}...")
df = yf.download(ticker, start=start_date, end=end_date)

# Fix for yfinance returning MultiIndex columns
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)


if df.empty:
    print("Error: No data found. Check ticker.")
    exit()

# 3. The Math (Feature Engineering)
# Simple Moving Average (50 days) - Shows the medium-term trend
df['SMA_50'] = ta.sma(df['Close'], length=50)

# RSI (Relative Strength Index) - The "Overbought/Oversold" meter
df['RSI'] = ta.rsi(df['Close'], length=14)

# 4. The Logic (Basic Strategy Signal)
# If Price > SMA_50 -> Uptrend. If RSI < 30 -> Cheap.
last_close = df['Close'].iloc[-1]
last_rsi = df['RSI'].iloc[-1]
last_sma = df['SMA_50'].iloc[-1]

print(f"\n--- ANALYSIS FOR {ticker} ---")
print(f"Current Price: ${last_close:.2f}")
print(f"RSI (0-100):   {last_rsi:.2f}")
print(f"Trend (SMA50): ${last_sma:.2f}")

if last_rsi < 30:
    print(">>> SIGNAL: OVERSOLD (Potential BUY opportunity)")
elif last_rsi > 70:
    print(">>> SIGNAL: OVERBOUGHT (High risk of drop)")
else:
    print(">>> SIGNAL: NEUTRAL")

# 5. The Visuals (Interactive Chart)
# This creates a professional financial chart
fig = go.Figure()

# Candlesticks
fig.add_trace(go.Candlestick(x=df.index,
                             open=df['Open'], high=df['High'],
                             low=df['Low'], close=df['Close'], name='Price'))

# SMA Line
fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'],
                         line=dict(color='orange', width=2), name='SMA 50'))

fig.update_layout(title=f'{ticker} Analysis',
                  yaxis_title='Price (USD)', xaxis_rangeslider_visible=False)
fig.show()
