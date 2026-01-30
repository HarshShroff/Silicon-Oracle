"""
10-Year Treasury Yield Tracker
The "Fear Gauge" for risk-off sentiment
"""

import streamlit as st
import requests
from typing import Optional, Dict
from datetime import datetime


def fetch_treasury_yield() -> Optional[Dict[str, any]]:
    """
    Fetch 10-Year Treasury Yield from Alpha Vantage.

    Returns:
        {
            'yield': float,
            'date': str,
            'change': float (change from previous day)
        }
    """
    try:
        api_key = st.secrets.get("alphavantage", {}).get("api_key")

        if not api_key:
            return None

        # Alpha Vantage Treasury Yield endpoint
        url = f"https://www.alphavantage.co/query?function=TREASURY_YIELD&interval=daily&maturity=10year&apikey={api_key}"

        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()

            # Parse the response
            if "data" in data and len(data["data"]) >= 2:
                latest = data["data"][0]
                previous = data["data"][1]

                current_yield = float(latest.get("value", 0))
                prev_yield = float(previous.get("value", 0))
                yield_date = latest.get("date", "")

                return {
                    'yield': current_yield,
                    'date': yield_date,
                    'change': current_yield - prev_yield
                }

        return None

    except Exception as e:
        # Silent fail
        return None


@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_treasury_yield_cached() -> Optional[Dict[str, any]]:
    """Cached version of treasury yield fetch."""
    return fetch_treasury_yield()


def render_treasury_widget():
    """Render Treasury Yield widget in sidebar."""
    yield_data = get_treasury_yield_cached()

    if not yield_data:
        return

    current_yield = yield_data['yield']
    change = yield_data['change']

    # Interpret the signal
    if current_yield >= 4.5:
        signal = "⚠️ High"
        signal_color = "#FF4B4B"
        interpretation = "Risk-off sentiment"
    elif current_yield <= 3.5:
        signal = "✅ Low"
        signal_color = "#00C805"
        interpretation = "Risk-on sentiment"
    else:
        signal = "➡️ Normal"
        signal_color = "#888888"
        interpretation = "Neutral"

    st.sidebar.divider()
    st.sidebar.subheader("Fear Gauge (10Y Treasury)")

    col1, col2 = st.sidebar.columns(2)

    with col1:
        st.metric(
            "Yield",
            f"{current_yield:.2f}%",
            delta=f"{change:.2f}%" if change != 0 else None,
            delta_color="inverse"  # Higher yield = worse for stocks
        )

    with col2:
        st.markdown(f"""
        <div style='padding: 5px; text-align: center;'>
            <div style='font-size: 12px; color: #888888;'>Signal</div>
            <div style='font-size: 18px; font-weight: bold; color: {signal_color};'>{signal}</div>
            <div style='font-size: 10px; color: #888888;'>{interpretation}</div>
        </div>
        """, unsafe_allow_html=True)

    # Explanation in expander
    with st.sidebar.expander("ℹ️ What is this?"):
        st.markdown("""
        **The 10-Year Treasury Yield** is the "risk-free rate."

        - **Rising Yield** → Money flows from stocks to bonds → Tech stocks fall
        - **Falling Yield** → Money flows from bonds to stocks → Tech stocks rally

        When this spikes above 4.5%, expect volatility in growth stocks like NVDA.
        """)
