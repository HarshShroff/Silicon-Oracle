import yfinance as yf
import pandas as pd
import pandas_ta_classic as ta
from sklearn.ensemble import RandomForestClassifier
from datetime import datetime, timedelta

# --- 1. DATA INGESTION (THE TRIFECTA) ---
TICKER = "NVDA"
MARKET_1 = "SPY"  # Broad Market
MARKET_2 = "QQQ"  # Tech Sector

print(f"--- FETCHING DATA FOR {TICKER}, {MARKET_1}, {MARKET_2} ---")
end_date = datetime.now()
start_date = end_date - timedelta(days=365*5)

tickers = [TICKER, MARKET_1, MARKET_2]
df_all = yf.download(tickers, start=start_date, end=end_date)['Close']

if isinstance(df_all.columns, pd.MultiIndex):
    df_all.columns = df_all.columns.get_level_values(0)

df = pd.DataFrame()
df['Close'] = df_all[TICKER]
df['SPY_Close'] = df_all[MARKET_1]
df['QQQ_Close'] = df_all[MARKET_2]

# --- 2. FEATURE ENGINEERING ---
# NVDA Indicators
df['RSI'] = ta.rsi(df['Close'], length=14)
df['SMA_50'] = ta.sma(df['Close'], length=50)
df['Dist_SMA'] = df['Close'] / df['SMA_50']

# SPY Context (Broad Market)
df['SPY_RSI'] = ta.rsi(df['SPY_Close'], length=14)

# QQQ Context (Tech Sector) -> THIS IS NEW
df['QQQ_SMA_50'] = ta.sma(df['QQQ_Close'], length=50)
df['QQQ_Trend'] = df['QQQ_Close'] / df['QQQ_SMA_50']
df['Tech_Strength'] = df['QQQ_Close'].pct_change() - df['SPY_Close'].pct_change()

df.dropna(inplace=True)

# --- 3. TARGET & TRAIN ---
df['Target'] = (df['Close'].shift(-1) > df['Close']).astype(int)

train_size = int(len(df) * 0.8)
train = df.iloc[:train_size]
test = df.iloc[train_size:]

# We give the AI more clues now
predictors = ["RSI", "Dist_SMA", "SPY_RSI", "QQQ_Trend", "Tech_Strength"]

# TWEAK: Lower estimators to prevent overfitting, deeper trees
model = RandomForestClassifier(
    n_estimators=100, min_samples_split=10, random_state=1)
model.fit(train[predictors], train["Target"])

# --- 4. SNIPER BACKTEST (RELAXED) ---
preds_proba = model.predict_proba(test[predictors])[:, 1]
preds_proba = pd.Series(preds_proba, index=test.index)

start_cash = 10000
cash = start_cash
shares = 0

# TWEAK: We lower the threshold slightly.
# If the AI sees QQQ is strong, 55% confidence is enough.
buy_threshold = 0.55
sell_threshold = 0.45

for date, prob in preds_proba.items():
    price = test.loc[date]['Close']

    if prob > buy_threshold and cash > 0:
        shares = cash / price
        cash = 0
    elif prob < sell_threshold and shares > 0:
        cash = shares * price
        shares = 0

final_val = cash + (shares * test.iloc[-1]['Close'])
ml_return = ((final_val - start_cash) / start_cash) * 100

bh_shares = start_cash / test.iloc[0]['Close']
bh_val = bh_shares * test.iloc[-1]['Close']
bh_return = ((bh_val - start_cash) / start_cash) * 100

print("\n--- SECTOR AWARE RESULTS ---")
print(f"Sniper Return:      {ml_return:.2f}%")
print(f"Buy & Hold Return:  {bh_return:.2f}%")
