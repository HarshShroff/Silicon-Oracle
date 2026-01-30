"""
Market Scanner - Multi-Ticker Analysis Engine
The "Radar" of Silicon Oracle
"""

import streamlit as st
import pandas as pd
import numpy as np
import pandas_ta_classic as ta
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.data import fetch_stock_data, get_data_fetcher


# --- WATCHLISTS ---
WATCHLISTS = {
    "AI/Tech": ["NVDA", "AMD", "MSFT", "GOOGL", "META", "AVGO", "TSM"],
    "Energy": ["VST", "URA", "XLE", "NEE", "CEG", "CCJ"],
    "Dividend": ["SCHD", "VYM", "O", "JEPI", "HDV"],
    "Speculative": ["PLTR", "SOFI", "COIN", "MSTR", "HOOD"],
    "ETFs": ["SPY", "QQQ", "IWM", "DIA", "VTI"],
    "Custom": []  # User can add their own
}


class MarketScanner:
    """Scans multiple tickers and ranks them by Oracle score."""

    def __init__(self):
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes

    def _fetch_data(self, ticker: str, period: str = "1y") -> Optional[pd.DataFrame]:
        """Fetch historical data for a ticker using Alpaca."""
        try:
            data = fetch_stock_data(ticker, period=period, interval="1d")
            if data is None or data.empty:
                return None
            return data[['Open', 'High', 'Low', 'Close', 'Volume']]
        except Exception as e:
            st.warning(f"Error fetching {ticker}: {e}")
            return None

    def _calculate_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate technical indicators for a dataframe."""
        if df is None or len(df) < 50:
            return None

        try:
            # SMA 50
            sma_50 = ta.sma(df['Close'], length=50)
            last_sma = float(
                sma_50.iloc[-1]) if sma_50 is not None and not sma_50.empty else None

            # RSI 14
            rsi = ta.rsi(df['Close'], length=14)
            last_rsi = float(
                rsi.iloc[-1]) if rsi is not None and not rsi.empty else 50

            # Current price
            last_price = float(df['Close'].iloc[-1])

            # Daily change
            daily_change = float(df['Close'].pct_change().iloc[-1]) * 100

            # Volatility (20-day std of returns, annualized)
            returns = df['Close'].pct_change().dropna()
            volatility = float(returns.tail(20).std() * np.sqrt(252) * 100)

            # Volume vs average
            avg_volume = df['Volume'].tail(20).mean()
            last_volume = df['Volume'].iloc[-1]
            volume_ratio = float(
                last_volume / avg_volume) if avg_volume > 0 else 1.0

            # 1M, 3M, 6M performance
            perf_1m = float(
                (df['Close'].iloc[-1] / df['Close'].iloc[-21] - 1) * 100) if len(df) > 21 else 0
            perf_3m = float(
                (df['Close'].iloc[-1] / df['Close'].iloc[-63] - 1) * 100) if len(df) > 63 else 0
            perf_6m = float(
                (df['Close'].iloc[-1] / df['Close'].iloc[-126] - 1) * 100) if len(df) > 126 else 0

            return {
                "price": last_price,
                "sma_50": last_sma,
                "rsi": last_rsi,
                "daily_change": daily_change,
                "volatility": volatility,
                "volume_ratio": volume_ratio,
                "perf_1m": perf_1m,
                "perf_3m": perf_3m,
                "perf_6m": perf_6m
            }
        except Exception as e:
            return None

    def _calculate_oracle_score(self, indicators: Dict[str, Any],
                                spy_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate Oracle score (0-3) based on indicators."""
        if not indicators or not spy_data:
            return {"score": 0, "reasons": ["Insufficient data"]}

        score = 0
        reasons = []

        # 1. Trend: Price > SMA50
        if indicators['sma_50'] and indicators['price'] > indicators['sma_50']:
            score += 1
            reasons.append("Price above SMA50 (Uptrend)")
        else:
            reasons.append("Price below SMA50 (Downtrend)")

        # 2. Momentum: RSI not overbought
        if indicators['rsi'] < 70:
            score += 1
            reasons.append(f"RSI {indicators['rsi']:.0f} - Not overbought")
        else:
            reasons.append(f"RSI {indicators['rsi']:.0f} - Overbought")

        # 3. Market Health: SPY above its SMA50
        if spy_data.get('sma_50') and spy_data.get('price'):
            if spy_data['price'] > spy_data['sma_50']:
                score += 1
                reasons.append("Market healthy (SPY > SMA50)")
            else:
                reasons.append("Market weak (SPY < SMA50)")

        return {
            "score": score,
            "reasons": reasons,
            "signal": "BUY" if score == 3 else ("WATCH" if score == 2 else "AVOID")
        }

    def scan_ticker(self, ticker: str, spy_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Scan a single ticker and return analysis."""
        df = self._fetch_data(ticker)
        if df is None:
            return None

        indicators = self._calculate_indicators(df)
        if not indicators:
            return None

        oracle = self._calculate_oracle_score(indicators, spy_data)

        return {
            "ticker": ticker,
            **indicators,
            **oracle
        }

    def scan_watchlist(self, tickers: List[str], progress_callback=None) -> List[Dict[str, Any]]:
        """Scan multiple tickers in parallel."""
        results = []

        # First, get SPY data for market context
        spy_df = self._fetch_data("SPY")
        spy_data = self._calculate_indicators(
            spy_df) if spy_df is not None else {}

        # Scan tickers in parallel
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(self.scan_ticker, ticker, spy_data): ticker
                       for ticker in tickers}

            completed = 0
            for future in as_completed(futures):
                ticker = futures[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    st.warning(f"Error scanning {ticker}: {e}")

                completed += 1
                if progress_callback:
                    progress_callback(completed / len(tickers))

        # Sort by score (descending), then by RSI (ascending for better entry)
        results.sort(key=lambda x: (-x['score'], x['rsi']))

        return results

    def get_relative_strength(self, tickers: List[str], period: str = "3mo") -> pd.DataFrame:
        """Calculate relative strength vs SPY using Alpaca."""
        try:
            fetcher = get_data_fetcher()
            all_tickers = list(set(tickers + ["SPY"]))

            # Fetch data for all tickers
            all_data = fetcher.get_multiple_bars(
                all_tickers, period=period, interval="1d")

            if not all_data or "SPY" not in all_data:
                return pd.DataFrame()

            spy_data = all_data["SPY"]
            spy_return = (spy_data['Close'].iloc[-1] /
                          spy_data['Close'].iloc[0] - 1) * 100

            # Calculate relative strength
            rs_data = []
            for ticker in tickers:
                ticker_upper = ticker.upper()
                if ticker_upper in all_data:
                    ticker_data = all_data[ticker_upper]
                    ticker_return = (
                        ticker_data['Close'].iloc[-1] / ticker_data['Close'].iloc[0] - 1) * 100
                    rs = ticker_return - spy_return
                    rs_data.append({
                        "ticker": ticker,
                        "return": ticker_return,
                        "spy_return": spy_return,
                        "relative_strength": rs,
                        "outperforming": rs > 0
                    })

            return pd.DataFrame(rs_data).sort_values('relative_strength', ascending=False)
        except Exception as e:
            st.error(f"Error calculating relative strength: {e}")
            return pd.DataFrame()

    def detect_volume_spikes(self, tickers: List[str], threshold: float = 2.0) -> List[Dict[str, Any]]:
        """Detect stocks with unusual volume (> threshold * average)."""
        spikes = []

        for ticker in tickers:
            df = self._fetch_data(ticker, period="3mo")
            if df is None or len(df) < 20:
                continue

            avg_volume = df['Volume'].tail(20).mean()
            last_volume = df['Volume'].iloc[-1]
            ratio = last_volume / avg_volume if avg_volume > 0 else 0

            if ratio >= threshold:
                spikes.append({
                    "ticker": ticker,
                    "volume": last_volume,
                    "avg_volume": avg_volume,
                    "ratio": ratio,
                    "price_change": float(df['Close'].pct_change().iloc[-1] * 100)
                })

        return sorted(spikes, key=lambda x: x['ratio'], reverse=True)


# --- STREAMLIT INTEGRATION ---

@st.cache_resource
def get_scanner() -> MarketScanner:
    """Get or create scanner instance."""
    return MarketScanner()


def render_scanner_tab():
    """Render the scanner interface."""
    scanner = get_scanner()

    st.header("Market Scanner")

    # --- MARKET MOVERS SECTION (NEW) ---
    try:
        from utils.market_movers import render_market_movers
        render_market_movers()
        st.divider()
    except Exception as e:
        pass  # Market movers may not be available

    st.subheader("Watchlist Scanner")

    # Watchlist selector
    col1, col2 = st.columns([2, 1])

    with col1:
        selected_watchlist = st.selectbox(
            "Select Watchlist",
            options=list(WATCHLISTS.keys()),
            index=0,
            key="scanner_main_watchlist_selector"
        )

    with col2:
        custom_tickers = st.text_input(
            "Add Custom Tickers",
            placeholder="AAPL, TSLA, ...",
            help="Comma-separated list of additional tickers",
            key="scanner_custom_tickers"
        )

    # Build ticker list
    tickers = WATCHLISTS[selected_watchlist].copy()
    if custom_tickers:
        custom_list = [t.strip().upper()
                       for t in custom_tickers.split(",") if t.strip()]
        tickers.extend(custom_list)
        tickers = list(set(tickers))  # Remove duplicates

    st.caption(f"Scanning {len(tickers)} tickers: {', '.join(tickers)}")

    # Scan button
    if st.button("Run Full Scan", type="primary", width='stretch'):
        progress_bar = st.progress(0, text="Scanning market...")

        def update_progress(pct):
            progress_bar.progress(pct, text=f"Scanning... {int(pct*100)}%")

        results = scanner.scan_watchlist(
            tickers, progress_callback=update_progress)
        progress_bar.empty()

        if results:
            st.session_state['scan_results'] = results
            st.success(f"Scan complete! Found {len(results)} stocks.")

    # Display results
    if 'scan_results' in st.session_state and st.session_state['scan_results']:
        results = st.session_state['scan_results']

        st.divider()
        st.subheader("Scan Results (Ranked by Oracle Score)")

        # Create results dataframe
        df = pd.DataFrame(results)

        # Signal color mapping
        def signal_color(signal):
            if signal == "BUY":
                return "🟢"
            elif signal == "WATCH":
                return "🟡"
            return "🔴"

        df['signal_icon'] = df['signal'].apply(signal_color)
        df['display_signal'] = df['signal_icon'] + " " + df['signal']

        # Format columns
        st.dataframe(
            df[['ticker', 'score', 'display_signal', 'price', 'rsi', 'daily_change',
                'perf_1m', 'volatility', 'volume_ratio']],
            column_config={
                "ticker": "Ticker",
                "score": st.column_config.NumberColumn("Score", format="%d/3"),
                "display_signal": "Signal",
                "price": st.column_config.NumberColumn("Price", format="$%.2f"),
                "rsi": st.column_config.NumberColumn("RSI", format="%.0f"),
                "daily_change": st.column_config.NumberColumn("Day %", format="%.2f%%"),
                "perf_1m": st.column_config.NumberColumn("1M %", format="%.1f%%"),
                "volatility": st.column_config.NumberColumn("Vol %", format="%.1f%%"),
                "volume_ratio": st.column_config.NumberColumn("Vol Ratio", format="%.1fx")
            },
            hide_index=True,
            width='stretch'
        )

        # Top picks section
        st.divider()
        buy_signals = [r for r in results if r['signal'] == 'BUY']

        if buy_signals:
            st.subheader("Top Picks (Score 3/3)")
            for stock in buy_signals[:3]:
                with st.expander(f"**{stock['ticker']}** - ${stock['price']:.2f}"):
                    st.write("**Why Buy:**")
                    for reason in stock['reasons']:
                        st.write(f"  {reason}")

                    col1, col2, col3 = st.columns(3)
                    col1.metric("RSI", f"{stock['rsi']:.0f}")
                    col2.metric("1M Return", f"{stock['perf_1m']:.1f}%")
                    col3.metric("Volatility", f"{stock['volatility']:.1f}%")
        else:
            st.info("No strong buy signals found. Market may be choppy.")

        # Volume spikes
        st.divider()
        st.subheader("Volume Alerts")

        with st.spinner("Checking for unusual volume..."):
            spikes = scanner.detect_volume_spikes(tickers, threshold=1.5)

        if spikes:
            for spike in spikes[:5]:
                icon = "📈" if spike['price_change'] > 0 else "📉"
                st.write(
                    f"{icon} **{spike['ticker']}**: {spike['ratio']:.1f}x normal volume "
                    f"({spike['price_change']:+.1f}% today)"
                )
        else:
            st.caption("No unusual volume detected")

        # Relative Strength
        st.divider()
        st.subheader("Relative Strength vs SPY (3M)")

        rs_df = scanner.get_relative_strength(tickers, period="3mo")
        if not rs_df.empty:
            # Top outperformers
            outperformers = rs_df[rs_df['outperforming'] == True].head(5)
            underperformers = rs_df[rs_df['outperforming'] == False].tail(5)

            col1, col2 = st.columns(2)

            with col1:
                st.write("**Leaders (Beating SPY)**")
                for _, row in outperformers.iterrows():
                    st.write(
                        f"🏆 {row['ticker']}: +{row['relative_strength']:.1f}% vs SPY")

            with col2:
                st.write("**Laggards (Trailing SPY)**")
                for _, row in underperformers.iterrows():
                    st.write(
                        f"📉 {row['ticker']}: {row['relative_strength']:.1f}% vs SPY")


def get_quick_scan_results(tickers: List[str]) -> Dict[str, Dict[str, Any]]:
    """Quick scan for getting current prices and basic info."""
    scanner = get_scanner()
    spy_df = scanner._fetch_data("SPY", period="6mo")
    spy_data = scanner._calculate_indicators(
        spy_df) if spy_df is not None else {}

    results = {}
    for ticker in tickers:
        result = scanner.scan_ticker(ticker, spy_data)
        if result:
            results[ticker] = result

    return results
