import yfinance as yf
import pandas as pd
import pandas_ta_classic as ta
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- SETUP ---
TICKER = "NVDA"
START_CASH = 10000
cash = START_CASH
position = 0  # How many shares we own
trade_log = []

# --- 1. GET DATA ---
end_date = datetime.now()
start_date = end_date - timedelta(days=730)
df = yf.download(TICKER, start=start_date, end=end_date)
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

# --- 2. INDICATORS UPDATE ---
df['SMA_20'] = ta.sma(df['Close'], length=20)  # Fast
df['SMA_50'] = ta.sma(df['Close'], length=50)  # Slow

# --- 3. THE BACKTEST ENGINE (GOLDEN CROSS) ---
print(f"--- STARTING BACKTEST FOR {TICKER} (GOLDEN CROSS) ---")
print(f"Initial Cash: ${cash}")

for i in range(50, len(df)):
    price = df['Close'].iloc[i]
    date = df.index[i]
    sma_fast = df['SMA_20'].iloc[i]
    sma_slow = df['SMA_50'].iloc[i]

    # We need the PREVIOUS day to detect a "Cross"
    prev_fast = df['SMA_20'].iloc[i-1]
    prev_slow = df['SMA_50'].iloc[i-1]

    # BUY SIGNAL: Fast crosses ABOVE Slow
    if prev_fast < prev_slow and sma_fast > sma_slow and position == 0:
        shares_to_buy = int(cash / price)
        if shares_to_buy > 0:
            cash -= shares_to_buy * price
            position += shares_to_buy
            trade_log.append(
                f"{date.date()}: BUY  {shares_to_buy} shares @ ${price:.2f}")

    # SELL SIGNAL: Fast crosses BELOW Slow
    elif prev_fast > prev_slow and sma_fast < sma_slow and position > 0:
        cash += position * price
        trade_log.append(
            f"{date.date()}: SELL {position} shares @ ${price:.2f}")
        position = 0

# --- 4. FINAL ACCOUNTING ---
# Sell everything at the end to see total value
final_value = cash + (position * df['Close'].iloc[-1])
profit = final_value - START_CASH
return_pct = (profit / START_CASH) * 100

# Calculate Buy & Hold Return (If you just bought on Day 1 and slept)
first_price = df['Close'].iloc[0]
buy_hold_shares = int(START_CASH / first_price)
buy_hold_value = buy_hold_shares * df['Close'].iloc[-1]
buy_hold_return = ((buy_hold_value - START_CASH) / START_CASH) * 100

print("\n--- RESULTS ---")
print(f"Strategy Final Value: ${final_value:.2f}")
print(f"Strategy Return:      {return_pct:.2f}%")
print(f"Buy & Hold Return:    {buy_hold_return:.2f}%")
print("-" * 30)

if final_value > buy_hold_value:
    print("🏆 RESULT: The Bot BEAT the Market!")
else:
    print("💀 RESULT: The Bot LOST to Buy & Hold.")
