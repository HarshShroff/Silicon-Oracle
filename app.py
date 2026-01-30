import streamlit as st
import numpy as np
import pandas as pd
import pandas_ta_classic as ta
import plotly.graph_objects as go
from datetime import datetime, timedelta
from scipy.stats import norm

from utils.quant import calculate_optimal_position
from utils.data import fetch_stock_data, fetch_latest_price, get_data_fetcher
from utils.godmode_data import get_complete_intelligence, get_chart_data, get_realtime_quote
from utils.godmode_ui import render_godmode_sidebar, render_insider_section, render_recommendation_trends, render_performance_chart
from utils.portfolio_history import get_portfolio_history
from utils.gemini import get_ai
from utils.alpaca import get_alpaca_trader, render_alpaca_account, render_trade_dialog, render_orders_tab
from scanner import render_scanner_tab, get_quick_scan_results
from portfolio import get_portfolio_manager, render_portfolio_sidebar, render_portfolio_tab
from datetime import datetime, timedelta
from scipy.stats import norm

# --- PAGE CONFIG ---
st.set_page_config(page_title="Silicon Oracle", page_icon="🔮", layout="wide")

# --- MOBILE-RESPONSIVE CSS ---
st.markdown("""
<style>
/* Mobile-first responsive design */
@media (max-width: 768px) {
    /* Stack columns vertically */
    .stColumns > div {
        flex: 100% !important;
        max-width: 100% !important;
    }

    /* Larger touch targets */
    .stButton > button {
        min-height: 48px;
        font-size: 16px;
    }

    /* Readable text */
    .stMarkdown {
        font-size: 14px;
    }

    /* Compact sidebar */
    .css-1d391kg {
        padding: 1rem 0.5rem;
    }

    /* Full-width charts */
    .stPlotlyChart {
        width: 100% !important;
    }

    /* Hide non-essential on mobile */
    .desktop-only {
        display: none;
    }

    /* Tab spacing for mobile */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
    }

    .stTabs [data-baseweb="tab"] {
        padding: 8px 12px;
        font-size: 14px;
    }
}

/* Touch-friendly inputs */
input, select, textarea {
    font-size: 16px !important;  /* Prevents iOS zoom */
}

/* Smooth animations */
.stButton > button {
    transition: all 0.2s ease;
}

.stButton > button:hover {
    transform: translateY(-1px);
}

/* Better contrast for metrics */
.stMetric {
    background: rgba(255, 255, 255, 0.05);
    padding: 10px;
    border-radius: 8px;
}
</style>
""", unsafe_allow_html=True)

# --- AUTHENTICATION CHECK ---
# For local development, we auto-login. For production, this shows login form.
try:
    from utils.auth import is_logged_in, render_login_form, render_user_menu, is_auth_enabled, enable_local_dev_mode, get_user_decrypted_keys, get_current_user
    from utils.database import is_supabase_enabled

    # If Supabase is not configured, enable local dev mode (no auth required)
    if not is_supabase_enabled():
        enable_local_dev_mode()

    # If auth is enabled and user is not logged in, show login form
    if is_auth_enabled() and not is_logged_in():
        render_login_form()
        st.stop()

    # --- BYOK PROMPT: Check if user needs to configure API keys ---
    # Only show once per session after login
    if is_logged_in() and not st.session_state.get('byok_checked'):
        st.session_state['byok_checked'] = True
        user_keys = get_user_decrypted_keys()

        # Check if essential keys are missing
        has_alpaca = bool(user_keys.get('alpaca_api_key')
                          and user_keys.get('alpaca_secret_key'))

        if not has_alpaca:
            st.warning(
                "**Welcome to Silicon Oracle!** Please configure your API keys in the Settings tab to unlock all features.")
            st.info(
                "Go to **Settings → API Keys** to add your Alpaca, Finnhub, and Gemini keys.")

except ImportError:
    # Auth module not available, continue without auth (local dev)
    pass

# --- AUTOREFRESH LOGIC ---
try:
    from streamlit_autorefresh import st_autorefresh
    from utils.godmode_data import get_market_status

    # Check market status
    status = get_market_status()
    is_open = status and status.get('is_open')

    # DISABLE AUTO-REFRESH DURING SCANNING to prevent page reload mid-scan
    # Check multiple conditions:
    # 1. Scanning in progress
    # 2. Scan requested (two-phase approach - set before rerun)
    # 3. User has scan results (likely reviewing AI guidance)
    is_scanning = st.session_state.get('oracle_scanning', False)
    scan_in_progress = st.session_state.get('scan_in_progress', False)
    scan_requested = st.session_state.get('scan_requested', False)
    has_scan_results = 'oracle_results' in st.session_state and st.session_state[
        'oracle_results']

    # Also check the regular scanner results
    has_scanner_results = 'scan_results' in st.session_state and st.session_state[
        'scan_results']

    # Disable auto-refresh if any scan-related activity
    disable_refresh = is_scanning or scan_in_progress or scan_requested or has_scan_results or has_scanner_results

    # Only enable auto-refresh if NOT in scanning mode and no results being viewed
    if not disable_refresh:
        # Refresh every 30s if market open, else every 5 mins (300000ms)
        refresh_interval = 30000 if is_open else 300000
        st_autorefresh(interval=refresh_interval, key="data_refresh")

    # --- EMAIL AUTOMATION TRIGGERS ---
    try:
        from utils.notifications import send_daily_digest, send_position_alert
        from utils.auth import get_current_user_id, get_user_decrypted_keys
        from utils.database import get_user_profile
        from datetime import datetime

        user_id = get_current_user_id()
        if user_id:
            profile = get_user_profile(user_id)
            # Check if user has enabled notifications
            if profile and profile.get('notifications_enabled'):
                keys = get_user_decrypted_keys()
                gmail = keys.get('gmail_address') or profile.get(
                    'gmail_address')
                # Need decrypted app password
                pwd = keys.get('gmail_app_password')
                if not pwd and profile.get('gmail_app_password_encrypted'):
                    from utils.encryption import decrypt_value
                    pwd = decrypt_value(
                        profile['gmail_app_password_encrypted'])

                if gmail and pwd:
                    now = datetime.now()

                    # 1. MORNING DIGEST (6:00 AM - 6:15 AM)
                    last_digest = st.session_state.get('last_digest_date')
                    if now.hour == 6 and now.minute < 15 and last_digest != now.date():
                        from utils.ai_scanner import get_oracle_scanner
                        scanner = get_oracle_scanner()
                        tickers = ["NVDA", "AMD", "MSFT", "AAPL", "TSLA"]
                        results = scanner.scan_watchlist(tickers)

                        # Sync portfolio for accurate summary
                        try:
                            from utils.alpaca import get_alpaca_trader
                            from portfolio import get_portfolio_manager, render_portfolio_sidebar
                            pm = get_portfolio_manager()
                            trader = get_alpaca_trader()
                            if trader.is_connected():
                                pm.sync_with_alpaca(trader)

                            summary = {
                                "portfolio_value": pm.get_portfolio_value({})['total_value'],
                                "buying_power": pm.get_cash(),
                                "daily_change": 0
                            }
                        except:
                            summary = {}

                        send_daily_digest(gmail, pwd, results[:5], summary)
                        st.session_state['last_digest_date'] = now.date()
                        st.toast("📧 Morning Digest Sent!")

                    # 2. POSITION ALERTS
                    # Only check if market is open to avoid noise
                    if is_open:
                        from portfolio import get_portfolio_manager
                        pm = get_portfolio_manager()
                        positions = pm.get_positions()
                        for pos in positions:
                            upl_pct = float(pos['unrealized_plpc'])
                            ticker = pos['ticker']

                            # Deduplicate alerts for the day
                            alert_key = f"alert_{ticker}_{now.date()}"
                            if alert_key not in st.session_state:
                                if upl_pct <= -10:
                                    send_position_alert(gmail, pwd, ticker, "STOP LOSS WARNING", float(
                                        pos['avg_price']), float(pos['current_price']), upl_pct)
                                    st.session_state[alert_key] = True
                                    st.toast(f"📧 Stop Loss: {ticker}")
                                elif upl_pct >= 20:
                                    send_position_alert(gmail, pwd, ticker, "TAKE PROFIT ALERT", float(
                                        pos['avg_price']), float(pos['current_price']), upl_pct)
                                    st.session_state[alert_key] = True
                                    st.toast(f"📧 Take Profit: {ticker}")

    except Exception as e:
        pass  # Fail silently
except:
    pass

# --- NAVIGATION TABS ---
tab_analysis, tab_scanner, tab_portfolio, tab_trade, tab_watchlist, tab_ai, tab_settings = st.tabs([
    "📊 Analysis", "🔍 Scanner", "💼 Portfolio", "📈 Trade", "👁 Watchlist", "🤖 AI Guide", "⚙️ Settings"
])

# --- SIDEBAR ---
st.sidebar.header("Configuration")

# Check if user clicked a peer stock button
if 'selected_ticker' in st.session_state:
    TICKER = st.session_state['selected_ticker']
    del st.session_state['selected_ticker']  # Clear after use
else:
    TICKER = st.sidebar.text_input("Stock Ticker", value="NVDA").upper()


MARKET = "SPY"  # S&P 500 ETF for market context
SECTOR = "QQQ"  # Nasdaq-100 ETF for tech sector context

# 🔥 GOD MODE: Fetch COMPLETE intelligence from all APIs
with st.spinner("Loading God Mode intelligence..."):
    intelligence = get_complete_intelligence(TICKER)

# Extract components
overview = intelligence.get('fundamentals')
quote = intelligence.get('quote')

# 🔥 GOD MODE SIDEBAR: Real-time quote, earnings, peers
render_godmode_sidebar(intelligence)

if overview:
    # Source Credit in sidebar
    st.sidebar.caption(f"📊 Data: {overview['source']} (Real-time)")
else:
    # Fallback to basic display if all sources fail
    st.sidebar.divider()
    st.sidebar.subheader("Fundamentals")
    st.sidebar.warning("Could not load company data")

# --- PORTFOLIO SIDEBAR ---
try:
    # SYNC WITH ALPACA (The "Mirror" Logic)
    # Ensure local DB matches actual Alpaca positions
    pm = get_portfolio_manager()
    trader = get_alpaca_trader()
    if trader.is_connected():
        pm.sync_with_alpaca(trader)

    render_portfolio_sidebar()
except Exception as e:
    pass  # Portfolio module may not be initialized yet

# --- ALPACA SIDEBAR ---
try:
    render_alpaca_account()
except Exception as e:
    pass  # Alpaca may not be connected

# --- TREASURY YIELD SIDEBAR ---
# TEMPORARILY DISABLED to avoid Alpha Vantage burst rate limit
# Re-enable after implementing proper rate limiting
# try:
#     render_treasury_widget()
# except Exception as e:
#     pass  # Treasury data may not be available

# --- 1. DATA LOADER (USING ALPACA) ---


@st.cache_data(ttl=60)
def load_data(ticker, period="2y"):
    """Load historical data using God Mode (yfinance first, fallback to Alpaca)."""
    try:
        # Try yfinance first (smooth, complete data)
        data = get_chart_data(ticker, period=period, interval="1d")
        if data is not None and not data.empty:
            return data

        # Fallback to Alpaca if yfinance fails
        data = fetch_stock_data(ticker, period=period, interval="1d")
        if data is None or data.empty:
            st.warning(f"No data returned for {ticker}")
            return pd.DataFrame()
        return data
    except Exception as e:
        st.error(f"Error fetching data for {ticker}: {e}")
        return pd.DataFrame()


@st.cache_resource
def load_sentiment_model():
    from transformers import pipeline
    return pipeline("sentiment-analysis", model="ProsusAI/finbert")


# Load Data
with st.spinner(f"Fetching data for {TICKER}..."):
    df = load_data(TICKER)
    df_spy = load_data(MARKET)
    df_qqq = load_data(SECTOR)

if df.empty or df_spy.empty or df_qqq.empty:
    st.error(
        "⚠️ Data fetching failed (Rate Limit or Invalid Ticker). Please try again in 1 minute.")
    st.stop()

# --- 2. TECHNICAL ANALYSIS (THE MATH) ---
df['SMA_50'] = ta.sma(df['Close'], length=50)
df['RSI'] = ta.rsi(df['Close'], length=14)

# Handle potential None returns from indicators if not enough data
if df['SMA_50'].isnull().all():
    df['SMA_50'] = df['Close']
if df['RSI'].isnull().all():
    df['RSI'] = 50

last_price = float(df['Close'].iloc[-1])
last_rsi = float(df['RSI'].iloc[-1])
last_sma = float(df['SMA_50'].iloc[-1])

# Market Context
spy_sma_series = ta.sma(df_spy['Close'], length=50)
if spy_sma_series is None or spy_sma_series.empty or spy_sma_series.isnull().all():
    spy_sma = df_spy['Close'].iloc[-1]
else:
    spy_sma = spy_sma_series.iloc[-1]

spy_price = df_spy['Close'].iloc[-1]
is_market_healthy = spy_price > spy_sma

# --- HELPER: CALCULATE SHARPE ---


def calculate_sharpe(data, risk_free_rate=0.045):
    # Daily returns
    returns = data['Close'].pct_change()
    # Excess daily returns (Return - Daily Risk Free Rate)
    excess_returns = returns - (risk_free_rate / 252)
    # Annualized Sharpe Ratio
    sharpe = np.sqrt(252) * (excess_returns.mean() / excess_returns.std())
    return sharpe

# --- MONTE CARLO SIMULATION ENGINE ---


def run_monte_carlo(data, days=30, simulations=1000):
    # Get historical stats
    log_returns = np.log(1 + data['Close'].pct_change())
    u = log_returns.mean()
    var = log_returns.var()
    drift = u - (0.5 * var)
    stdev = log_returns.std()

    # Pre-compute current price
    last_price = data['Close'].iloc[-1]

    # Generate random shocks (The Chaos)
    # Z is a matrix of random numbers [days, simulations]
    Z = np.random.rand(days, simulations)

    # Calculate future daily returns
    daily_returns = np.exp(drift + stdev * norm.ppf(Z))

    # Create price paths
    price_paths = np.zeros_like(daily_returns)
    price_paths[0] = last_price

    for t in range(1, days):
        price_paths[t] = price_paths[t-1] * daily_returns[t]

    return price_paths


# --- DASHBOARD METRICS ---
sharpe_ratio = calculate_sharpe(df)

# ============================================
# TAB 1: ANALYSIS (Original Dashboard)
# ============================================
with tab_analysis:
    st.title(f"🔮 {TICKER} Analysis")

    # 🔥 GOD MODE: Display REAL-TIME price from Finnhub
    if quote:
        realtime_price = quote['current']
        realtime_change = quote['change']
        realtime_change_pct = quote['percent_change']

        # Big real-time price display
        st.markdown(f"### ${realtime_price:.2f}")
        change_color = "green" if realtime_change >= 0 else "red"
        st.markdown(
            f":{change_color}[{realtime_change:+.2f} ({realtime_change_pct:+.2f}%) • Finnhub Live]")
    elif overview:
        # Fallback to yfinance
        st.markdown(f"### ${last_price:.2f}")
        st.caption("Using delayed data")

    # 52-Week Range (only in Analysis tab)
    if overview:
        try:
            current_price = quote.get(
                'current', 0) if quote else overview.get('day_high', 0)
            low = overview.get('year_low', 0)
            high = overview.get('year_high', 0)

            if current_price and high > low and low > 0:
                progress = (current_price - low) / (high - low)
                progress = max(0.0, min(1.0, progress))

                st.write("**52-Week Range**")
                st.progress(progress)
                range_col1, range_col2, range_col3 = st.columns(3)
                with range_col1:
                    st.caption(f"Low: ${low:.2f}")
                with range_col2:
                    if progress < 0.3:
                        st.caption("🔵 Near 52-week low")
                    elif progress > 0.7:
                        st.caption("🔴 Near 52-week high")
                    else:
                        st.caption("⚪ Mid-range")
                with range_col3:
                    st.caption(f"High: ${high:.2f}")
        except:
            pass

    st.divider()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        # Use real-time price if available, otherwise historical
        display_price = quote['current'] if quote else last_price
        st.metric("Current Price", f"${display_price:.2f}",
                  f"{df['Close'].pct_change().iloc[-1]:.2%}")

    with col2:
        # Sharpe Logic: > 1 is Good, > 2 is Great, < 1 is Bad
        sharpe_color = "normal"
        if sharpe_ratio > 2:
            sharpe_color = "normal"  # Greenish default
            sharpe_label = "🌟 EXCELLENT"
        elif sharpe_ratio > 1:
            sharpe_color = "off"
            sharpe_label = "✅ GOOD"
        else:
            sharpe_color = "inverse"
            sharpe_label = "⚠️ POOR"

        st.metric("Sharpe Ratio (1Y)",
                  f"{sharpe_ratio:.2f}", sharpe_label, delta_color=sharpe_color)

    with col3:
        rsi_delta = last_rsi - 50
        st.metric("RSI (Momentum)", f"{last_rsi:.2f}",
                  delta=f"{rsi_delta:.2f}", delta_color="inverse")

    with col4:
        trend_color = "normal"
        if last_price > last_sma:
            trend_label = "🚀 UPTREND"
            trend_delta = "Above SMA50"
            trend_color = "normal"
        else:
            trend_label = "📉 DOWNTREND"
            trend_delta = "Below SMA50"
            trend_color = "inverse"
        st.metric("Trend (SMA 50)", trend_label,
                  trend_delta, delta_color=trend_color)

    st.divider()

    # --- 3. CHARTS (DYNAMIC TIMEFRAME) ---
    st.subheader(f"Price Action: {TICKER}")

    # 1. Timeframe Selector
    timeframe = st.radio(
        "Zoom Level",
        options=["1D", "5D", "1M", "6M", "1Y", "5Y"],
        index=0,  # Default to 1D for real-time view
        horizontal=True,
        label_visibility="collapsed"
    )

    # Auto-refresh for intraday views (1D)
    if timeframe == "1D":
        col_ref1, col_ref2 = st.columns([1, 4])
        with col_ref1:
            live_mode = st.toggle(
                "Live Updates", value=True, help="Refresh every 30s")

        if live_mode:
            st.caption("⚡ Live")
            from streamlit_autorefresh import st_autorefresh as auto_refresh
            # 30 seconds refresh
            auto_refresh(interval=30000, limit=None,
                         key=f"refresh_{timeframe}_live")
        else:
            st.caption("⏸️ Paused")

    # 2. Logic to map Timeframe -> Alpaca Parameters
    period_map = {
        "1D": {"period": "1d", "interval": "5m"},
        "5D": {"period": "5d", "interval": "15m"},
        "1M": {"period": "1mo", "interval": "1d"},
        "6M": {"period": "6mo", "interval": "1d"},
        # "YTD": {"period": "6mo", "interval": "1d"},  # Approximate YTD
        "1Y": {"period": "1y", "interval": "1d"},
        "5Y": {"period": "5y", "interval": "1d"},
        # "Max": {"period": "5y", "interval": "1d"},  # Alpaca max ~5 years free
    }

    params = period_map[timeframe]

    # 3. Fetch Chart-Specific Data with short cache for real-time feel
    @st.cache_data(ttl=25)
    def fetch_chart_data_optimized(ticker, period, interval):
        """Fetch chart data - God Mode (yfinance first, fallback to Alpaca)."""
        # Try yfinance first (smooth, no gaps)
        data = get_chart_data(ticker, period=period, interval=interval)
        if data is not None and not data.empty:
            return data

        # Fallback to Alpaca for intraday/recent data
        return fetch_stock_data(ticker, period=period, interval=interval)

    try:
        chart_df = fetch_chart_data_optimized(
            TICKER, params['period'], params['interval'])

        if chart_df is None or chart_df.empty:
            st.error("No data available for this timeframe.")
            st.stop()

        # Handle timezone for Alpaca data (yfinance is already correct)
        try:
            import pytz
            if chart_df.index.tz is not None:
                chart_df.index = chart_df.index.tz_convert('America/New_York')
            elif not hasattr(chart_df.index, 'tz') or chart_df.index.tz is None:
                # Likely from yfinance, already in correct timezone
                pass
        except:
            pass  # Proceed with data as-is

        # 4. Plot Area Chart (Google Finance style)
        if not chart_df.empty:
            fig = go.Figure()

            start_p = float(chart_df['Close'].iloc[0])
            end_p = float(chart_df['Close'].iloc[-1])

            if end_p >= start_p:
                line_color = '#00C805'
                fill_color = 'rgba(0, 200, 5, 0.2)'
            else:
                line_color = '#FF5000'
                fill_color = 'rgba(255, 80, 0, 0.2)'

            price_min = float(chart_df['Close'].min())
            price_max = float(chart_df['Close'].max())
            price_range = price_max - price_min
            if price_range < 0.01:
                price_range = price_max * 0.02
            y_padding = price_range * 0.1
            y_min = price_min - y_padding
            y_max = price_max + y_padding

            close_prices = chart_df['Close'].tolist()
            x_values = chart_df.index.tolist()

            fig.add_trace(go.Scatter(
                x=x_values,
                y=close_prices,
                mode='lines',
                line=dict(color=line_color, width=2.5),
                fill='tozeroy',
                fillcolor=fill_color,
                name='Price',
                hovertemplate='%{x}<br>$%{y:.2f}<extra></extra>'
            ))

            fig.update_layout(
                height=500,
                hovermode="x unified",
                margin=dict(l=10, r=70, t=20, b=40),
                xaxis=dict(
                    showgrid=False,
                    showline=False,
                    showspikes=True,
                    spikethickness=1,
                    spikedash='solid',
                    spikecolor='#555555',
                    spikemode='across',
                    tickfont=dict(color='#888888')
                ),
                yaxis=dict(
                    showgrid=True,
                    gridcolor='rgba(255,255,255,0.1)',
                    side="right",
                    tickprefix="$",
                    tickformat=".2f",
                    range=[y_min, y_max],
                    showspikes=True,
                    spikethickness=1,
                    spikedash='solid',
                    spikecolor='#555555',
                    spikemode='across',
                    tickfont=dict(color='#888888')
                ),
                showlegend=False,
                plot_bgcolor='#0E1117',
                paper_bgcolor='#0E1117'
            )

            st.plotly_chart(fig, width='stretch')

            # Statistics Row
            latest = chart_df.iloc[-1]
            s1, s2, s3, s4, s5 = st.columns(5)
            s1.metric("Open", f"${latest['Open']:.2f}")
            s2.metric("High", f"${latest['High']:.2f}")
            s3.metric("Low", f"${latest['Low']:.2f}")
            s4.metric("Volume", f"{latest['Volume']/1e6:.1f}M")
            s5.metric("Close", f"${latest['Close']:.2f}")

            st.divider()

    except Exception as e:
        st.error(f"Error loading chart: {e}")

    # --- MONTE CARLO PROJECTION ---
    st.subheader("🎲 Monte Carlo Simulation (Next 30 Days)")

    if st.button("Run Simulation (1,000 Paths)", key="mc_btn"):
        st.session_state['run_mc'] = True

    if st.session_state.get('run_mc'):
        with st.spinner("Simulating future realities..."):
            sim_days = 30
            last_date = df.index[-1]
            future_dates = pd.date_range(
                start=last_date + timedelta(days=1), periods=sim_days, freq='B')

            price_paths = run_monte_carlo(df, days=sim_days, simulations=1000)

            final_prices = price_paths[-1]
            mean_price = np.mean(final_prices)
            p5 = np.percentile(final_prices, 5)
            p95 = np.percentile(final_prices, 95)

            fig_mc = go.Figure()

            for i in range(50):
                fig_mc.add_trace(go.Scatter(
                    x=future_dates,
                    y=price_paths[:, i],
                    mode='lines',
                    line=dict(width=1, color='rgba(0, 255, 255, 0.15)'),
                    showlegend=False,
                    hoverinfo='skip'
                ))

            fig_mc.add_trace(go.Scatter(
                x=future_dates,
                y=np.mean(price_paths, axis=1),
                mode='lines',
                line=dict(width=4, color='white'),
                name="Average Path"
            ))

            fig_mc.update_layout(
                title=f"Projected Price Cone ({sim_days} Days)",
                yaxis_title="Projected Price (USD)",
                xaxis_title="Future Date",
                template="plotly_dark",
                height=500,
                hovermode="x unified"
            )

            st.plotly_chart(fig_mc, width='stretch')

            col_mc1, col_mc2, col_mc3 = st.columns(3)
            col_mc1.metric("Worst Case (5%)", f"${p5:.2f}")
            col_mc2.metric("Most Likely", f"${mean_price:.2f}")
            col_mc3.metric("Best Case (95%)", f"${p95:.2f}")

    # 🔥 GOD MODE: VERIFIED NEWS & INSIDERS (NO HALLUCINATIONS)

    # 1. Real-time News (Benzinga/Alpaca)
    # render_news_section(intelligence)

    # 2. Insider Activity (Finnhub)
    render_insider_section(intelligence)

    st.divider()

    # --- AI ANALYSIS (GOOGLE GROUNDED) ---
    st.subheader("🤖 AI Oracle Analysis (Google Grounded)")

    if st.button("Generate AI Deep Dive"):
        with st.spinner("Searching Google for real-time intelligence..."):
            ai = get_ai()
            analysis, score, label = ai.analyze_ticker(TICKER)

            # Render Gauge
            st.metric("AI Sentiment Score", f"{label}", f"{score}/100")
            st.progress(score)

            # Render Analysis
            st.markdown(analysis)
            st.caption("ℹ️ Sources: Google Search (Real-Time)")

    # 🔥 GOD MODE: FINNHUB INTELLIGENCE SECTIONS
    st.divider()

    # Analyst Recommendations & Upside
    rec_trends = intelligence.get('recommendation_trends')
    if rec_trends:
        render_recommendation_trends(intelligence)
        st.divider()

    # --- THE ORACLE'S RECOMMENDATION (COMPREHENSIVE MULTI-FACTOR) ---
    st.subheader("🔮 The Oracle's Final Verdict")

    # DYNAMIC SCORING: Track both score and max_possible_score
    # Only factors with actual data contribute to max_possible_score
    # This prevents ETFs/stocks without certain data from being penalized
    # Using a dict to allow modification from nested function
    scoring = {"score": 0.0, "max": 0.0}
    factors = []

    # Helper to add factor with dynamic max tracking
    def add_factor(icon, signal, detail, color, points_earned, points_possible, has_data=True):
        """Add a factor to the scoring system.

        Args:
            has_data: If False, this factor is N/A and doesn't count toward max
        """
        factors.append((icon, signal, detail, color))
        if has_data:
            scoring["score"] += points_earned
            scoring["max"] += points_possible

    # 1. TECHNICAL TREND (Trend is King) - Max: 1.0
    # Use App calculations first, fallback to Intelligence backup
    sma50 = last_sma

    # Fallback to Intelligence (Layer 2)
    if sma50 is None or pd.isna(sma50):
        tech = intelligence.get('technicals', {})
        sma50 = tech.get('sma_50')
        if tech.get('rsi'):
            last_rsi = tech.get('rsi')

    # If we have data, score it
    if sma50 and last_price:
        if last_price > sma50:
            add_factor("📈 Trend", "Bullish",
                       "Price is above SMA 50", "green", 1.0, 1.0)
        else:
            add_factor("📉 Trend", "Bearish",
                       "Price is below SMA 50", "red", 0.0, 1.0)
    else:
        add_factor("📈 Trend", "N/A", "Insufficient Data (ETF/New)",
                   "gray", 0, 0, has_data=False)

    # 2. MOMENTUM (RSI) - Max: 1.0
    if last_rsi and not pd.isna(last_rsi):
        if last_rsi < 30:
            add_factor("⚡ Momentum", "Bullish",
                       "RSI is Oversold (Bargain)", "green", 1.0, 1.0)
        elif last_rsi < 70:
            add_factor("⚡ Momentum", "Neutral/Bullish",
                       "RSI is Healthy", "green", 1.0, 1.0)
        else:
            add_factor("⚡ Momentum", "Bearish",
                       "RSI is Overbought", "red", 0.0, 1.0)
    else:
        add_factor("⚡ Momentum", "N/A", "No RSI Data",
                   "gray", 0, 0, has_data=False)

    # 3. MARKET CONTEXT (Rising Tide) - Max: 1.0
    # Market context is always available (SPY data)
    if is_market_healthy:
        add_factor("🌊 Market", "Bullish",
                   "S&P 500 is in an Uptrend", "green", 1.0, 1.0)
    else:
        add_factor("🌊 Market", "Risk-Off", "S&P 500 is Weak", "red", 0.0, 1.0)

    # 4. ANALYST CONSENSUS - Max: 1.0
    rec_trends = intelligence.get('recommendation_trends', [])
    if rec_trends:
        latest = rec_trends[0]
        total_analysts = sum(
            [latest.get(k, 0) for k in ['strongBuy', 'buy', 'hold', 'sell', 'strongSell']])
        if total_analysts > 0:
            w_score = ((latest.get('strongBuy', 0)*5) + (latest.get('buy', 0)*4) +
                       (latest.get('hold', 0)*3) + (latest.get('sell', 0)*2) +
                       (latest.get('strongSell', 0)*1)) / total_analysts

            if w_score >= 3.5:
                add_factor("🧠 Analysts", "Bullish",
                           f"Consensus Rating: {w_score:.1f}/5.0", "green", 1.0, 1.0)
            elif w_score <= 2.5:
                add_factor("🧠 Analysts", "Bearish",
                           f"Consensus Rating: {w_score:.1f}/5.0", "red", 0.0, 1.0)
            else:
                add_factor("🧠 Analysts", "Neutral",
                           "Consensus is Hold", "gray", 0.5, 1.0)
        else:
            # ETFs typically don't have analyst coverage - mark as N/A
            add_factor("🧠 Analysts", "N/A", "No Analyst Coverage (ETF)",
                       "gray", 0, 0, has_data=False)
    else:
        add_factor("🧠 Analysts", "N/A", "No Analyst Data",
                   "gray", 0, 0, has_data=False)

    # 5. INSIDER ACTIVITY - Max: 1.0
    # ETFs don't have insider trading - mark as N/A if no data
    insiders = intelligence.get('insiders', [])
    if insiders and len(insiders) > 0:
        insider_buy_val = sum([t['share']*t['transactionPrice']
                              for t in insiders if t.get('change', 0) > 0])
        insider_sell_val = sum([t['share']*t['transactionPrice']
                               for t in insiders if t.get('change', 0) < 0])

        if insider_buy_val > insider_sell_val:
            add_factor("🕵️ Insiders", "Bullish",
                       "Net Insider Buying Detected", "green", 1.0, 1.0)
        elif insider_sell_val > (insider_buy_val * 2):
            add_factor("🕵️ Insiders", "Bearish",
                       "Heavy Insider Selling", "red", 0.0, 1.0)
        else:
            add_factor("🕵️ Insiders", "Neutral",
                       "Mixed Activity", "gray", 0.5, 1.0)
    else:
        # ETFs don't have insiders - this is N/A, not negative
        add_factor("🕵️ Insiders", "N/A", "No Insider Data (ETF/Fund)",
                   "gray", 0, 0, has_data=False)

    # 6. PRICE TARGET UPSIDE - Max: 1.0
    # ETFs typically don't have analyst price targets
    quote = intelligence.get('quote')
    price_targets = intelligence.get('price_targets')
    if quote and price_targets:
        current_price = quote.get('current') or 0
        target_mean = price_targets.get('target_mean')

        if current_price and target_mean and current_price > 0 and target_mean > 0:
            upside_pct = ((target_mean - current_price) / current_price) * 100

            if upside_pct >= 15:
                add_factor("💰 Target", "Bullish",
                           f"{upside_pct:+.1f}% Upside to Analyst Target", "green", 1.0, 1.0)
            elif upside_pct >= 5:
                add_factor("💰 Target", "Neutral",
                           f"{upside_pct:+.1f}% Upside (Modest)", "gray", 0.5, 1.0)
            elif upside_pct >= -5:
                add_factor("💰 Target", "Neutral",
                           f"{upside_pct:+.1f}% Near Target", "gray", 0.5, 1.0)
            else:
                add_factor("💰 Target", "Bearish",
                           f"{upside_pct:.1f}% Downside Risk", "red", 0.0, 1.0)
        else:
            add_factor("💰 Target", "N/A", "No Price Target (ETF/Fund)",
                       "gray", 0, 0, has_data=False)
    else:
        add_factor("💰 Target", "N/A", "No Price Target Data",
                   "gray", 0, 0, has_data=False)

    # 7. VALUATION METRICS (P/E, PEG from fundamentals) - Max: 1.0
    # ETFs don't have P/E or PEG ratios - mark as N/A
    fundamentals = intelligence.get('fundamentals', {})
    has_valuation_data = False
    if fundamentals:
        pe_ratio = fundamentals.get('pe_ratio', 'N/A')
        peg_ratio = fundamentals.get('peg_ratio', 'N/A')

        # PEG is king for growth stocks (< 1 is undervalued, > 2 is overvalued)
        if isinstance(peg_ratio, (int, float)) and peg_ratio > 0:
            has_valuation_data = True
            if peg_ratio < 1:
                add_factor("📊 Valuation", "Bullish",
                           f"PEG Ratio: {peg_ratio:.2f} (Undervalued)", "green", 1.0, 1.0)
            elif peg_ratio < 2:
                add_factor("📊 Valuation", "Neutral",
                           f"PEG Ratio: {peg_ratio:.2f} (Fair)", "gray", 0.5, 1.0)
            else:
                add_factor("📊 Valuation", "Bearish",
                           f"PEG Ratio: {peg_ratio:.2f} (Expensive)", "red", 0.0, 1.0)
        elif isinstance(pe_ratio, (int, float)) and pe_ratio > 0:
            # Fallback to P/E if PEG unavailable
            has_valuation_data = True
            if pe_ratio < 15:
                add_factor("📊 Valuation", "Bullish",
                           f"P/E: {pe_ratio:.1f} (Low)", "green", 0.75, 1.0)
            elif pe_ratio < 25:
                add_factor("📊 Valuation", "Neutral",
                           f"P/E: {pe_ratio:.1f} (Fair)", "gray", 0.5, 1.0)
            else:
                add_factor("📊 Valuation", "Neutral",
                           f"P/E: {pe_ratio:.1f} (High Growth)", "gray", 0.25, 1.0)

    if not has_valuation_data:
        # ETFs don't have traditional valuation metrics - this is N/A
        add_factor("📊 Valuation", "N/A", "No Valuation Data (ETF/Fund)",
                   "gray", 0, 0, has_data=False)

    # 8. EARNINGS PROXIMITY - Max: 0.5
    # ETFs don't report earnings - mark as N/A
    earnings = intelligence.get('earnings')
    if earnings and earnings.get('date'):
        from datetime import datetime, timedelta
        try:
            earn_date_str = earnings.get('date', '')
            earn_date = datetime.strptime(earn_date_str, '%Y-%m-%d')
            today = datetime.now()
            days_until = (earn_date - today).days

            if days_until < 0:
                add_factor("📅 Earnings", "Neutral",
                           "Earnings Already Passed", "gray", 0.25, 0.5)
            elif days_until <= 7:
                add_factor("📅 Earnings", "Caution",
                           f"Earnings in {days_until} days (High Vol)", "orange", 0.0, 0.5)
            elif days_until <= 30:
                add_factor("📅 Earnings", "Neutral",
                           f"Earnings in {days_until} days", "gray", 0.25, 0.5)
            else:
                add_factor("📅 Earnings", "Clear",
                           f"Earnings {days_until} days out", "green", 0.5, 0.5)
        except:
            add_factor("📅 Earnings", "N/A", "Date Format Error",
                       "gray", 0, 0, has_data=False)
    else:
        # ETFs don't have earnings - this is N/A, not negative
        add_factor("📅 Earnings", "N/A", "No Earnings (ETF/Fund)",
                   "gray", 0, 0, has_data=False)

    # 9. NEWS SENTIMENT - Max: 1.0
    news_items = intelligence.get('news', [])
    if news_items and len(news_items) >= 3:
        # Simple keyword-based sentiment (upgrade this to proper NLP later)
        bullish_words = ['surge', 'gain', 'beat', 'upgrade',
                         'bullish', 'buy', 'strong', 'growth', 'rally', 'high']
        bearish_words = ['drop', 'fall', 'miss', 'downgrade',
                         'bearish', 'sell', 'weak', 'loss', 'decline', 'low']

        sentiment_score = 0
        for item in news_items[:5]:  # Analyze top 5 recent articles
            headline = item.get('headline', '').lower()
            summary = item.get('summary', '').lower()
            text = headline + ' ' + summary

            for word in bullish_words:
                if word in text:
                    sentiment_score += 1
            for word in bearish_words:
                if word in text:
                    sentiment_score -= 1

        if sentiment_score >= 3:
            add_factor("📰 News", "Bullish",
                       "Positive Media Coverage", "green", 1.0, 1.0)
        elif sentiment_score <= -3:
            add_factor("📰 News", "Bearish",
                       "Negative Media Coverage", "red", 0.0, 1.0)
        else:
            add_factor("📰 News", "Neutral",
                       "Mixed Media Sentiment", "gray", 0.5, 1.0)
    else:
        # Not enough news is N/A (common for smaller stocks/ETFs)
        add_factor("📰 News", "N/A", "Insufficient News Data",
                   "gray", 0, 0, has_data=False)

    # 10. DIVIDEND YIELD - Max: 0.5 (bonus factor)
    if fundamentals:
        div_yield = fundamentals.get('dividend_yield', 0)
        if isinstance(div_yield, (int, float)) and div_yield > 0:
            # Convert to percent if in decimal form (yfinance returns 0.03 for 3%)
            div_pct = div_yield * 100 if div_yield < 1 else div_yield
            if div_pct >= 3:
                add_factor("💵 Dividend", "Bullish",
                           f"{div_pct:.2f}% Yield (Income)", "green", 0.5, 0.5)
            elif div_pct >= 1:
                add_factor("💵 Dividend", "Neutral",
                           f"{div_pct:.2f}% Yield", "gray", 0.25, 0.5)
            else:
                add_factor("💵 Dividend", "Neutral",
                           f"{div_pct:.2f}% Yield (Low)", "gray", 0.1, 0.5)
        else:
            # Many growth stocks don't pay dividends - this is neutral, not negative
            add_factor("💵 Dividend", "N/A", "No Dividend (Growth Stock)",
                       "gray", 0, 0, has_data=False)
    else:
        add_factor("💵 Dividend", "N/A", "No Dividend Data",
                   "gray", 0, 0, has_data=False)

    # --- RENDER VERDICT ---
    col_v1, col_v2 = st.columns([1, 1.5])

    with col_v1:
        st.caption("COMPREHENSIVE CONFIDENCE SCORE")

        # DYNAMIC SCORING: Calculate percentage based on AVAILABLE factors only
        # This prevents ETFs from being penalized for missing data
        if scoring["max"] > 0:
            final_pct = max(
                0, min(100, (scoring["score"] / scoring["max"]) * 100))
        else:
            final_pct = 50  # Default to neutral if no data available

        st.progress(final_pct / 100)

        # Show both the score and what it's out of (for transparency)
        available_factors = sum(1 for f in factors if f[1] != "N/A")
        total_factors = len(factors)
        st.caption(
            f"Score: {scoring['score']:.1f} / {scoring['max']:.1f} ({available_factors}/{total_factors} factors)")

        # PERCENTAGE-BASED THRESHOLDS (consistent regardless of available factors)
        # This ensures ETFs with fewer factors are judged fairly
        if final_pct >= 75:
            st.success("## 🚀 STRONG BUY")
            st.write(
                "High conviction setup. Multiple factors aligning across all intelligence sources.")
        elif final_pct >= 55:
            st.info("## 🟢 BUY / ACCUMULATE")
            st.write(
                "Positive outlook with majority factors supporting. Good risk/reward.")
        elif final_pct >= 40:
            st.warning("## 🟡 HOLD / WATCH")
            st.write(
                "Conflicting signals. Wait for clearer setup or do more research.")
        elif final_pct >= 25:
            st.error("## 🔴 AVOID")
            st.write("Negative factors dominate. High risk environment.")
        else:
            st.error("## 🔴 STRONG SELL")
            st.write("Extremely bearish setup. Multiple red flags detected.")

    with col_v2:
        st.write("### 📋 Decision Matrix")
        for f in factors:
            icon, signal, desc, color = f
            st.markdown(f"**{icon}** : :{color}[**{signal}**] — _{desc}_")


# ============================================
# TAB 2: SCANNER
# ============================================
with tab_scanner:
    render_scanner_tab()


# ============================================
# TAB 3: PORTFOLIO (ACTIONABLE EDITION)
# ============================================
with tab_portfolio:
    st.header("💼 Portfolio Command")

    # --- SYNC STATUS ---
    pm = get_portfolio_manager()
    trade_count = len(pm.get_trade_history(limit=1000))
    st.caption(
        f"🔄 Auto-sync: 30s during market hours | Last: {datetime.now().strftime('%I:%M:%S %p')} | {trade_count} trades synced")

    # --- SECTION 1: PERFORMANCE TRACKER ---
    p_col1, p_col2 = st.columns([3, 1])
    with p_col2:
        period = st.selectbox(
            "History Period", ["1D", "1W", "1M", "1Y", "ALL"], index=0)

    with st.spinner("Loading account history..."):
        tf = "1D"
        if period == "1D":
            tf = "5Min"

        history_df = get_portfolio_history(period, tf)
        render_performance_chart(history_df)

    st.divider()

    # --- SECTION 2: ACTIVE HOLDINGS (WITH BUTTONS) ---
    trader = get_alpaca_trader()

    if trader:
        positions = trader.get_positions()

        if positions:
            st.subheader(f"📊 Active Positions ({len(positions)})")

            # 1. THE HEADER ROW
            # We use columns to create a table-like header
            h1, h2, h3, h4, h5 = st.columns([1.5, 1, 1.5, 1.5, 1.5])
            h1.markdown("**Ticker**")
            h2.markdown("**Qty**")
            h3.markdown("**Value**")
            h4.markdown("**P/L**")
            h5.markdown("**Action**")

            st.markdown("---")  # Divider line

            # 2. THE DATA ROWS
            for p in positions:
                # robust extraction (handles both dict and object types)
                if isinstance(p, dict):
                    sym = p.get('symbol') or p.get('ticker')
                    qty = float(p.get('qty') or p.get('shares', 0))
                    val = float(p.get('market_value', 0))
                    pl = float(p.get('unrealized_pl', 0))
                    pl_pct = float(p.get('unrealized_plpc', 0))
                else:
                    sym = p.symbol
                    qty = float(p.qty)
                    val = float(p.market_value)
                    pl = float(p.unrealized_pl)
                    pl_pct = float(p.unrealized_plpc)

                # Create a row
                c1, c2, c3, c4, c5 = st.columns([1.5, 1, 1.5, 1.5, 1.5])

                with c1:
                    st.markdown(f"**{sym}**")

                with c2:
                    st.write(f"{qty:.2f}")

                with c3:
                    st.write(f"${val:,.2f}")

                with c4:
                    # Color code the P/L
                    color = "green" if pl >= 0 else "red"
                    st.markdown(f":{color}[${pl:+,.2f} ({pl_pct:+.2f}%)]")

                with c5:
                    # THE EJECT BUTTON 🛑
                    # We create a unique key for every button using the symbol
                    if st.button(f"🛑 Close", key=f"btn_close_{sym}", type="secondary"):
                        with st.spinner(f"Closing {sym}..."):
                            # Logic: Submit a Market Sell for the full quantity
                            try:
                                trader.submit_order(
                                    sym, qty, "sell", "market", "day")
                                st.success(f"Sold {qty} {sym}!")
                                st.rerun()  # Refresh to remove the row
                            except Exception as e:
                                st.error(f"Failed: {e}")

                st.divider()  # Line between rows

        else:
            st.info("You have no open positions. Use the Scanner to find trades!")
    else:
        st.error("⚠️ Alpaca Not Connected. Check your keys.")

    # --- SECTION 3: TRADE HISTORY (FROM LOCAL DB - SYNCED FROM ALPACA) ---
    st.subheader("📜 Trade History")

    pm = get_portfolio_manager()
    trades = pm.get_trade_history(limit=50)

    if trades:
        trades_df = pd.DataFrame(trades)

        # Format timestamp for display
        if 'timestamp' in trades_df.columns:
            trades_df['timestamp'] = pd.to_datetime(
                trades_df['timestamp']).dt.strftime('%Y-%m-%d %H:%M')

        # Color-code buy/sell
        st.dataframe(
            trades_df[['timestamp', 'ticker', 'action',
                       'shares', 'price', 'total_value', 'reason']],
            column_config={
                "timestamp": "Date/Time",
                "ticker": "Ticker",
                "action": "Action",
                "shares": st.column_config.NumberColumn("Shares", format="%.4f"),
                "price": st.column_config.NumberColumn("Price", format="$%.2f"),
                "total_value": st.column_config.NumberColumn("Total", format="$%.2f"),
                "reason": "Source"
            },
            hide_index=True,
            width='stretch'
        )

        # Performance metrics
        st.caption("📊 Performance Summary")
        perf = pm.get_performance_metrics()
        perf_col1, perf_col2, perf_col3, perf_col4 = st.columns(4)
        with perf_col1:
            st.metric("Total Trades", perf['total_trades'])
        with perf_col2:
            st.metric("Win Rate", f"{perf['win_rate']:.1f}%")
        with perf_col3:
            st.metric("Wins/Losses", f"{perf['wins']}/{perf['losses']}")
        with perf_col4:
            pnl_color = "normal" if perf['total_realized_pnl'] >= 0 else "inverse"
            st.metric("Realized P&L", f"${perf['total_realized_pnl']:,.2f}")
    else:
        st.caption(
            "No trade history yet. Execute trades via the Trade tab, then sync!")

    # --- SECTION 4: ACCOUNT VALUE CHART ---
    account_history = pm.get_account_history(limit=100)
    if account_history and len(account_history) > 1:
        st.caption("📈 Portfolio Value Over Time")
        ah_df = pd.DataFrame(account_history)
        ah_df['timestamp'] = pd.to_datetime(ah_df['timestamp'])
        ah_df = ah_df.sort_values('timestamp')

        # Calculate dynamic y-axis range (like Price Action chart)
        val_min = float(ah_df['portfolio_value'].min())
        val_max = float(ah_df['portfolio_value'].max())
        val_range = val_max - val_min
        if val_range < 1:  # Handle flat values
            val_range = val_max * 0.02
        y_padding = val_range * 0.1
        y_min = val_min - y_padding
        y_max = val_max + y_padding

        # Determine color based on performance
        start_val = float(ah_df['portfolio_value'].iloc[0])
        end_val = float(ah_df['portfolio_value'].iloc[-1])
        if end_val >= start_val:
            line_color = '#00d4aa'
            fill_color = 'rgba(0, 212, 170, 0.2)'
        else:
            line_color = '#FF5000'
            fill_color = 'rgba(255, 80, 0, 0.2)'

        # Create a clean line chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=ah_df['timestamp'],
            y=ah_df['portfolio_value'],
            mode='lines',
            name='Portfolio Value',
            line=dict(color=line_color, width=2),
            fill='tozeroy',
            fillcolor=fill_color,
            hovertemplate='%{x}<br>$%{y:,.2f}<extra></extra>'
        ))

        fig.update_layout(
            height=200,
            margin=dict(l=0, r=0, t=10, b=0),
            xaxis=dict(showgrid=False, title=''),
            yaxis=dict(
                showgrid=True,
                gridcolor='rgba(128,128,128,0.2)',
                title='',
                tickprefix='$',
                range=[y_min, y_max]  # Dynamic range like Price Action
            ),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            showlegend=False,
            hovermode='x unified'
        )

        st.plotly_chart(fig, width='stretch',
                        config={'displayModeBar': False})

# ============================================
# TAB 4: TRADE
# ============================================

with tab_trade:
    st.header("⚡ Quant Execution Desk")

    # Use the global TICKER variable to ensure consistency with the Sidebar
    ticker = TICKER

    # 1. Get Account Info
    trader = get_alpaca_trader()
    account = trader.get_account()

    if account:
        if isinstance(account, dict):
            bp = account.get('buying_power', 0)
        else:
            bp = getattr(account, 'buying_power', 0)
        buying_power = float(bp)
        st.metric("Buying Power", f"${buying_power:,.2f}")
    else:
        buying_power = 0
        st.error("Alpaca not connected.")

    st.divider()

    # 2. Portfolio Optimizer
    st.subheader("🧠 Position Sizer")

    # Check for Stale Data (If user switched ticker, clear old results)
    # This now correctly compares TSLA (current) vs NVDA (old state)
    if 'opt_ticker' in st.session_state and st.session_state.opt_ticker != ticker:
        if 'opt_result' in st.session_state:
            del st.session_state['opt_result']  # Delete old data

    c1, c2 = st.columns([1, 2])
    with c1:
        risk_profile = st.selectbox(
            "Risk Profile", ["Conservative", "Moderate", "Aggressive"], index=1,
            key="trade_risk_profile")

    # Calculate Button
    if st.button(f"🧮 Calculate Size for {ticker}"):
        with st.spinner(f"Crunching volatility metrics for {ticker}..."):
            opt = calculate_optimal_position(
                ticker, buying_power, risk_profile)

            if opt:
                st.session_state['opt_result'] = opt
                # Save WHICH stock we calculated
                st.session_state['opt_ticker'] = ticker
                st.rerun()
            else:
                st.error(f"❌ Could not retrieve volatility data for {ticker}.")

    # Display Results (Only if data exists AND matches current ticker)
    if 'opt_result' in st.session_state and st.session_state.get('opt_ticker') == ticker:
        res = st.session_state['opt_result']

        st.info(
            f"Analysis for **{ticker}** @ ${res['current_price']:.2f} (Vol: {res['annual_volatility']:.1f}%)")

        k1, k2 = st.columns(2)
        with k1:
            st.markdown(f"#### 🛡️ Safe Bet")
            st.markdown(f"**{res['vol_sizing']['shares']} Shares**")
            st.caption(f"Value: ${res['vol_sizing']['value']:,.2f}")
            if st.button("Use Safe Size"):
                st.session_state['trade_qty'] = res['vol_sizing']['shares']

        with k2:
            st.markdown(f"#### 🚀 Kelly Bet")
            st.markdown(f"**{res['kelly_sizing']['shares']} Shares**")
            st.caption(f"Value: ${res['kelly_sizing']['value']:,.2f}")
            if st.button("Use Kelly Size"):
                st.session_state['trade_qty'] = res['kelly_sizing']['shares']

    elif 'opt_result' in st.session_state:
        # If result exists but doesn't match ticker
        st.warning(
            f"⚠️ Displaying old data for {st.session_state.opt_ticker}. Click Calculate to update for {ticker}.")

    st.divider()

    # 3. Execution Terminal
    st.subheader("🔫 Execute Trade")

    col_qty, col_side = st.columns(2)
    with col_qty:
        qty_val = st.session_state.get('trade_qty', 1)
        quantity = st.number_input("Shares", min_value=1, value=int(qty_val))
    with col_side:
        side = st.selectbox("Side", ["BUY", "SELL"])

    if st.button(f"CONFIRM {side} {quantity} {ticker}", type="primary"):
        with st.spinner("Sending order to Alpaca..."):
            order = trader.submit_order(ticker, quantity, side)
            if order:
                order_id = order.id if hasattr(
                    order, 'id') else order.get('id', 'Unknown')
                st.success(f"✅ Order Filled! ID: {order_id}")
                st.balloons()
                st.cache_data.clear()

# ============================================
# TAB 5: WATCHLIST
# ============================================
with tab_watchlist:
    st.header("👁 Watchlists")
    st.caption("Track your favorite stocks and sync with Alpaca")

    # Watchlist management
    try:
        from utils.alpaca import get_alpaca_trader

        trader = get_alpaca_trader()

        # Local watchlists (from scanner.py)
        from scanner import WATCHLISTS

        col1, col2 = st.columns([2, 1])

        with col1:
            selected_list = st.selectbox(
                "Select Watchlist",
                options=list(WATCHLISTS.keys()),
                index=0,
                key="watchlist_tab_selector"
            )

        with col2:
            if st.button("Sync with Alpaca", width='stretch', key="sync_alpaca_btn"):
                if trader.is_connected():
                    with st.spinner("Syncing with Alpaca..."):
                        # Get Alpaca watchlists
                        alpaca_watchlists = trader.get_watchlists()

                        # Check if a watchlist with this name exists
                        existing = next(
                            (wl for wl in alpaca_watchlists if wl['name'] == selected_list), None)

                        if existing:
                            # Update existing watchlist
                            wl_id = existing['id']
                            # API returns 'assets' not 'symbols'
                            current_symbols = set(existing.get('assets', []))
                            new_symbols = set(
                                WATCHLISTS.get(selected_list, []))

                            added = []
                            removed = []

                            # Add new symbols
                            for symbol in new_symbols - current_symbols:
                                if trader.add_to_watchlist(wl_id, symbol):
                                    added.append(symbol)

                            # Remove old symbols
                            for symbol in current_symbols - new_symbols:
                                if trader.remove_from_watchlist(wl_id, symbol):
                                    removed.append(symbol)

                            msg = f"Synced '{selected_list}' with Alpaca!"
                            if added:
                                msg += f"\n  Added: {', '.join(added)}"
                            if removed:
                                msg += f"\n  Removed: {', '.join(removed)}"
                            if not added and not removed:
                                msg += "\n  (Already in sync)"
                            st.success(msg)
                        else:
                            # Create new watchlist
                            symbols = WATCHLISTS.get(selected_list, [])
                            result = trader.create_watchlist(
                                selected_list, symbols)
                            if result:
                                st.success(
                                    f"Created '{selected_list}' in Alpaca with {len(symbols)} stocks:\n  {', '.join(symbols)}")
                            else:
                                st.error(
                                    "Failed to create watchlist in Alpaca. Check the logs.")
                else:
                    st.error(
                        "Not connected to Alpaca. Check your API keys in Settings.")

        # Display watchlist
        tickers = WATCHLISTS.get(selected_list, [])

        if tickers:
            st.write(f"**{len(tickers)} stocks in {selected_list}:**")

            # Quick scan the watchlist
            from scanner import get_quick_scan_results

            with st.spinner("Fetching latest data..."):
                scan_results = get_quick_scan_results(tickers)

            if scan_results:
                # Create display dataframe
                display_data = []
                for ticker, data in scan_results.items():
                    display_data.append({
                        "Ticker": ticker,
                        "Price": f"${data.get('price', 0):.2f}",
                        "Day %": f"{data.get('daily_change', 0):+.2f}%",
                        "RSI": f"{data.get('rsi', 50):.0f}",
                        "Signal": data.get('signal', 'N/A'),
                        "Score": f"{data.get('score', 0)}/3"
                    })

                df = pd.DataFrame(display_data)
                st.dataframe(df, hide_index=True, width='stretch')

                # Quick actions
                st.divider()
                st.write("**Quick Actions:**")
                action_cols = st.columns(4)

                for i, ticker in enumerate(tickers[:4]):
                    with action_cols[i]:
                        if st.button(f"Analyze {ticker}", key=f"wl_analyze_{ticker}"):
                            st.session_state['selected_ticker'] = ticker
                            st.rerun()
        else:
            st.info("This watchlist is empty. Add tickers in the Scanner tab.")

        # Add custom ticker
        st.divider()
        st.subheader("Add to Watchlist")
        new_ticker = st.text_input("Ticker Symbol", placeholder="AAPL")
        if st.button("Add Ticker") and new_ticker:
            ticker_upper = new_ticker.strip().upper()
            if ticker_upper not in WATCHLISTS["Custom"]:
                WATCHLISTS["Custom"].append(ticker_upper)
                st.success(f"Added {ticker_upper} to Custom watchlist!")
            else:
                st.warning(f"{ticker_upper} is already in Custom watchlist.")

    except Exception as e:
        st.error(f"Error loading watchlist: {e}")

# ============================================
# SENTINEL DASHBOARD REDIRECT
# ============================================
# Use Flask routing for the full Sentinel Dashboard
# This block is just a visible link in the sidebar or main area if needed
# (Already handled by the "Sentinel" link in the HTML sidebar in Flask templates)


# ============================================
# TAB 6: AI GUIDANCE
# ============================================
with tab_ai:
    try:
        from utils.ai_scanner import render_ai_guidance_tab
        render_ai_guidance_tab()
    except ImportError as e:
        st.header("🤖 AI Guidance")
        st.warning("AI Scanner module not available. Check utils/ai_scanner.py")
        st.error(f"Import error: {e}")
    except Exception as e:
        st.header("🤖 AI Guidance")
        st.error(f"Error loading AI Guidance: {e}")


# ============================================
# TAB 7: SETTINGS
# ============================================
with tab_settings:
    try:
        from pages.settings import render_settings_page
        render_settings_page()
    except ImportError as e:
        st.header("⚙️ Settings")
        st.warning("Settings module not available.")
        st.error(f"Import error: {e}")
    except Exception as e:
        st.header("⚙️ Settings")
        st.error(f"Error loading Settings: {e}")

# --- USER MENU IN SIDEBAR ---
try:
    from utils.auth import render_user_menu
    render_user_menu()
except ImportError:
    pass
