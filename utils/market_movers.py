"""
Market Movers Scanner (Alpaca Edition)
Find Top Gainers & Losers using the Unlimited "God Mode" Data API
"""

import streamlit as st
import pandas as pd
from typing import Optional, Dict
from utils.godmode_data import get_market_movers


def render_market_movers():
    """Render Market Movers section in Scanner tab."""
    st.subheader("🚀 Market Movers (Live & Uncapped)")
    st.caption(
        "Top gainers & losers across the entire US market (Source: Alpaca)")

    movers_data = get_market_movers()

    if not movers_data:
        st.warning(
            "Market movers data unavailable. Check Alpaca connection.")
        return

    # Create two columns for gainers and losers
    col1, col2 = st.columns(2)

    # --- TOP GAINERS ---
    with col1:
        st.markdown("### 📈 Top Gainers")

        if 'gainers' in movers_data and not movers_data['gainers'].empty:
            df_gainers = movers_data['gainers'].copy()
            # Sort by change desc just in case
            df_gainers = df_gainers.sort_values(
                'change_percentage', ascending=False).head(10)

            # Format for display
            df_gainers['change_pct_display'] = df_gainers['change_percentage'].apply(
                lambda x: f"+{float(x):.2f}%"
            )
            df_gainers['price_display'] = df_gainers['price'].apply(
                lambda x: f"${x:.2f}"
            )

            # Simple ticker display if volume is missing
            display_df = df_gainers[[
                'ticker', 'price_display', 'change_pct_display']]
            display_df.columns = ['Ticker', 'Price', 'Change']

            # Style the dataframe
            st.dataframe(
                display_df,
                hide_index=True,
                width='stretch',
                height=400
            )
        else:
            st.info("No gainers data available")

    # --- TOP LOSERS ---
    with col2:
        st.markdown("### 📉 Top Losers")

        if 'losers' in movers_data and not movers_data['losers'].empty:
            df_losers = movers_data['losers'].copy()
            # Sort by change asc
            df_losers = df_losers.sort_values(
                'change_percentage', ascending=True).head(10)

            # Format for display
            df_losers['change_pct_display'] = df_losers['change_percentage'].apply(
                lambda x: f"{float(x):.2f}%"
            )
            df_losers['price_display'] = df_losers['price'].apply(
                lambda x: f"${x:.2f}"
            )

            display_df = df_losers[[
                'ticker', 'price_display', 'change_pct_display']]
            display_df.columns = ['Ticker', 'Price', 'Change']

            # Style the dataframe
            st.dataframe(
                display_df,
                hide_index=True,
                width='stretch',
                height=400
            )
        else:
            st.info("No losers data available")

    # Market temperature indicator
    st.divider()

    if 'gainers' in movers_data and not movers_data['gainers'].empty and 'losers' in movers_data and not movers_data['losers'].empty:
        # Calculate market temp based on average magnitude of moves
        avg_gain = movers_data['gainers']['change_percentage'].astype(
            float).mean()
        avg_loss = abs(movers_data['losers']
                       ['change_percentage'].astype(float).mean())

        market_temp = avg_gain / (avg_gain + avg_loss) * 100  # 0-100 scale

        if market_temp >= 60:
            temp_label = "🔥 Hot (Risk-On)"
            temp_color = "#00C805"
        elif market_temp <= 40:
            temp_label = "❄️ Cold (Risk-Off)"
            temp_color = "#FF4B4B"
        else:
            temp_label = "🌡️ Neutral"
            temp_color = "#888888"

        col_temp1, col_temp2, col_temp3 = st.columns(3)

        with col_temp1:
            st.markdown(f"""
            <div style='padding: 15px; border-radius: 5px; background-color: rgba(255,255,255,0.05); text-align: center;'>
                <div style='font-size: 14px; color: #888888;'>Market Temperature</div>
                <div style='font-size: 28px; font-weight: bold; color: {temp_color};'>{temp_label}</div>
                <div style='font-size: 12px; color: #888888;'>{market_temp:.1f}/100</div>
            </div>
            """, unsafe_allow_html=True)

        with col_temp2:
            st.metric("Avg Gainer", f"+{avg_gain:.2f}%")

        with col_temp3:
            st.metric("Avg Loser", f"-{avg_loss:.2f}%")
