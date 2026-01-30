import yfinance as yf
# from transformers import pipeline # Lazy loaded now
import pandas as pd

# 1. SETUP THE BRAIN (FinBERT)
# This downloads a ~400MB model. It might take a minute the first time.
print("Loading AI Model (FinBERT)...")
try:
    from transformers import pipeline
    classifier = pipeline("sentiment-analysis", model="ProsusAI/finbert")
except Exception as e:
    print(f"Error loading AI model: {e}")
    exit()

# 2. GET THE NEWS
TICKER = "NVDA"
print(f"Fetching News for {TICKER}...")
stock = yf.Ticker(TICKER)
news_list = stock.news  # Returns a list of latest articles

# 3. ANALYZE EACH HEADLINE
results = []

print(f"Found {len(news_list)} articles.")
print(f"\n--- LIVE SENTIMENT REPORT FOR {TICKER} ---")

for article in news_list:
    headline = article.get('title')
    if not headline and 'content' in article:
        headline = article['content'].get('title')

    if not headline:
        print("Skipping article with no title")
        continue

    print(f"Analyzing: {headline[:50]}...")

    # FinBERT gives us: Label (Positive/Negative/Neutral) and Score (Confidence)
    sentiment = classifier(headline)[0]

    print(f"Title: {headline}")
    print(f"Mood:  {sentiment['label']} ({sentiment['score']:.2%})")
    print("-" * 30)

    results.append({
        "Title": headline,
        "Label": sentiment['label'],
        "Score": sentiment['score']
    })

# 4. AGGREGATE THE VIBE
df = pd.DataFrame(results)

# Count the vibes
sentiment_counts = df['Label'].value_counts()
print("\n--- SUMMARY ---")
print(sentiment_counts)

# Simple Logic: If mostly Positive -> BULLISH. If mostly Negative -> BEARISH.
if "positive" in sentiment_counts and sentiment_counts["positive"] > len(df)/2:
    print(">>> NEWS VERDICT: 🚀 BULLISH")
elif "negative" in sentiment_counts and sentiment_counts["negative"] > len(df)/2:
    print(">>> NEWS VERDICT: 🩸 BEARISH")
else:
    print(">>> NEWS VERDICT: 🤷 NEUTRAL (Mixed signals)")
