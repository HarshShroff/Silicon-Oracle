import yfinance as yf
import pandas as pd
import pandas_ta_classic as ta
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import precision_score
from datetime import datetime, timedelta

# --- 1. DATA INGESTION ---
TICKER = "NVDA"
print(f"--- TRAINING AI MODEL FOR {TICKER} ---")

# We need MORE data for ML to learn patterns (5 Years)
end_date = datetime.now()
start_date = end_date - timedelta(days=365*5)
df = yf.download(TICKER, start=start_date, end=end_date)
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

# --- 2. FEATURE ENGINEERING (The "Sensors") ---
# RSI: Momentum
df['RSI'] = ta.rsi(df['Close'], length=14)
# SMA Ratio: Is price extended? (e.g. 1.1 means 10% above trend)
df['SMA_50'] = ta.sma(df['Close'], length=50)
df['Dist_SMA'] = df['Close'] / df['SMA_50']
# Daily Return: Did we go up or down yesterday?
df['Pct_Change'] = df['Close'].pct_change()

# CLEANUP: Drop NaN values created by indicators
df.dropna(inplace=True)

# --- 3. THE TARGET (The "Answer Key") ---
# We want to predict if Tomorrow's Close > Today's Close
# shift(-1) looks into the future 1 day
df['Target'] = (df['Close'].shift(-1) > df['Close']).astype(int)

# --- 4. TRAIN/TEST SPLIT ---
# We can't use random split (time series!). We train on the past, test on recent.
# Train on first 4 years, Test on last 1 year
train_size = int(len(df) * 0.8)
train = df.iloc[:train_size]
test = df.iloc[train_size:]

predictors = ["RSI", "Dist_SMA", "Pct_Change"]

# # --- 5. THE BRAIN (Random Forest) ---
# # n_estimators=100 (100 Decision Trees voting)
# # min_samples_split=10 (Prevent overfitting)
# model = RandomForestClassifier(
#     n_estimators=100, min_samples_split=10, random_state=1)
# model.fit(train[predictors], train["Target"])

# # --- 6. THE PREDICTION ---
# preds = model.predict(test[predictors])
# preds = pd.Series(preds, index=test.index)

# # Check Accuracy: When we said "Buy", did it actually go up?
# precision = precision_score(test["Target"], preds)
# print(f"AI Precision Score: {precision:.2%}")
# print("(This means: When the AI said 'UP', it was right X% of the time)")

# # --- 7. BACKTEST SIMULATION ---
# # Strategy: If Pred == 1, Buy/Hold. If Pred == 0, Sell/Cash.
# start_cash = 10000
# cash = start_cash
# shares = 0
# trade_log = []

# for date, row in test.iterrows():
#     prediction = preds.loc[date]
#     price = row['Close']

#     # AI Says UP -> Buy if we have cash
#     if prediction == 1 and cash > 0:
#         shares = cash / price
#         cash = 0

#     # AI Says DOWN -> Sell if we have shares
#     elif prediction == 0 and shares > 0:
#         cash = shares * price
#         shares = 0

# # Final Value
# final_val = cash + (shares * test.iloc[-1]['Close'])
# ml_return = ((final_val - start_cash) / start_cash) * 100

# # Buy & Hold Benchmark (for the same Test period)
# bh_shares = start_cash / test.iloc[0]['Close']
# bh_val = bh_shares * test.iloc[-1]['Close']
# bh_return = ((bh_val - start_cash) / start_cash) * 100

# print("\n--- TEST YEAR RESULTS (Last 12 Months) ---")
# print(f"AI Model Return:   {ml_return:.2f}%")
# print(f"Buy & Hold Return: {bh_return:.2f}%")

# if ml_return > bh_return:
#     print("🏆 RESULT: AI WINS (Smart Trading)")
# else:
#     print("💀 RESULT: AI LOST (Market too strong)")

# --- 5. THE BRAIN (TUNED) ---
# We increase n_estimators to 200 for more "voting" power
model = RandomForestClassifier(
    n_estimators=200, min_samples_split=50, random_state=1)
model.fit(train[predictors], train["Target"])

# --- 6. THE PREDICTION (PROBABILITY) ---
# Instead of Yes/No, we get % Confidence
preds_proba = model.predict_proba(test[predictors])
# Probability of "UP" class
preds_proba = pd.Series(preds_proba[:, 1], index=test.index)

# --- 7. SNIPER BACKTEST SIMULATION ---
start_cash = 10000
cash = start_cash
shares = 0
buy_threshold = 0.60  # Only buy if 60% sure
sell_threshold = 0.40  # Sell if confidence drops below 40%

print(f"\n--- RUNNING SNIPER LOGIC (Threshold: {buy_threshold*100}%) ---")

for date, prob in preds_proba.items():
    price = test.loc[date]['Close']

    # SNIPER BUY: Confidence is HIGH (> 60%)
    if prob > buy_threshold and cash > 0:
        shares = cash / price
        cash = 0
        # print(f"  {date.date()} BUY  (Conf: {prob:.2f})") # Uncomment to see trades

    # SNIPER SELL: Confidence is LOW (< 40%)
    elif prob < sell_threshold and shares > 0:
        cash = shares * price
        shares = 0
        # print(f"  {date.date()} SELL (Conf: {prob:.2f})")

# Final Value
final_val = cash + (shares * test.iloc[-1]['Close'])
ml_return = ((final_val - start_cash) / start_cash) * 100

# Buy & Hold Benchmark
bh_shares = start_cash / test.iloc[0]['Close']
bh_val = bh_shares * test.iloc[-1]['Close']
bh_return = ((bh_val - start_cash) / start_cash) * 100

print("\n--- SNIPER RESULTS ---")
print(
    f"AI Precision (Raw): {precision_score(test['Target'], (preds_proba > 0.5).astype(int)):.2%}")
print(f"Sniper Return:      {ml_return:.2f}%")
print(f"Buy & Hold Return:  {bh_return:.2f}%")

if ml_return > bh_return:
    print("🏆 RESULT: SNIPER WINS (Quality over Quantity)")
else:
    print("💀 RESULT: Still losing (Need better Data)")
