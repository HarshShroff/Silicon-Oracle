"""
Settings Page - BYOK API Key Management & User Preferences
"""
import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
from utils.auth import (
    get_current_user, is_logged_in, get_user_decrypted_keys,
    save_user_api_keys, clear_api_keys_cache
)
from utils.database import (
    get_user_profile, update_user_profile, is_supabase_enabled,
    get_user_positions, get_user_trades, get_user_watchlists,
    get_scan_results, get_account_history
)
from utils.notifications import render_notification_settings


def export_user_data(user_id: str):
    """Export all user data to CSV files and provide download."""
    st.subheader("Export Your Data")

    with st.spinner("Gathering your data..."):
        export_data = {}

        # 1. Profile data (excluding encrypted keys)
        profile = get_user_profile(user_id)
        if profile:
            # Remove sensitive fields
            safe_profile = {k: v for k, v in profile.items()
                          if not k.endswith('_encrypted') and k != 'id'}
            export_data['profile'] = pd.DataFrame([safe_profile])

        # 2. Positions
        positions = get_user_positions(user_id)
        if positions:
            export_data['positions'] = pd.DataFrame(positions)

        # 3. Trade history
        trades = get_user_trades(user_id, limit=1000)
        if trades:
            export_data['trades'] = pd.DataFrame(trades)

        # 4. Watchlists
        watchlists = get_user_watchlists(user_id)
        if watchlists:
            export_data['watchlists'] = pd.DataFrame(watchlists)

        # 5. AI Scan results
        scan_results = get_scan_results(user_id, limit=100)
        if scan_results:
            export_data['ai_scans'] = pd.DataFrame(scan_results)

        # 6. Account history
        account_history = get_account_history(user_id, limit=500)
        if account_history:
            export_data['account_history'] = pd.DataFrame(account_history)

    if not export_data:
        st.warning("No data found to export.")
        return

    st.success(f"Found {len(export_data)} data tables to export.")

    # Show preview
    for name, df in export_data.items():
        with st.expander(f"{name.title()} ({len(df)} records)"):
            st.dataframe(df.head(5), hide_index=True)

    # Create download buttons for each table
    st.write("**Download CSV Files:**")

    cols = st.columns(min(3, len(export_data)))
    for i, (name, df) in enumerate(export_data.items()):
        csv = df.to_csv(index=False)
        cols[i % 3].download_button(
            label=f"Download {name}.csv",
            data=csv,
            file_name=f"silicon_oracle_{name}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            key=f"download_{name}"
        )

    # Combined export (all tables in one Excel file)
    st.divider()
    st.write("**Download All Data (Excel):**")

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for name, df in export_data.items():
            df.to_excel(writer, sheet_name=name, index=False)

    st.download_button(
        label="Download All Data (Excel)",
        data=output.getvalue(),
        file_name=f"silicon_oracle_export_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="download_all_excel"
    )


def render_settings_page():
    """Render the settings page."""
    st.header("Settings")

    user = get_current_user()

    if not user:
        st.warning("Please log in to access settings.")
        return

    st.write(f"**Logged in as:** {user.get('email', 'Unknown')}")

    # Tabs for different settings
    tab1, tab2, tab3 = st.tabs(["API Keys", "Notifications", "Preferences"])

    # ============================================
    # TAB 1: API KEYS (BYOK)
    # ============================================
    with tab1:
        render_api_keys_settings()

    # ============================================
    # TAB 2: NOTIFICATIONS
    # ============================================
    with tab2:
        render_notification_settings()

    # ============================================
    # TAB 3: PREFERENCES
    # ============================================
    with tab3:
        render_preferences_settings()


def render_api_keys_settings():
    """Render API keys configuration section."""
    st.subheader("API Keys (BYOK)")
    st.caption("Bring Your Own Keys - Your keys are encrypted and stored securely")

    # Get current decrypted keys
    current_keys = get_user_decrypted_keys()

    # Status indicators
    col1, col2, col3 = st.columns(3)

    with col1:
        alpaca_status = "Connected" if current_keys.get(
            'alpaca_api_key') else "Not Set"
        st.metric("Alpaca", alpaca_status, delta="Paper Trading")

    with col2:
        finnhub_status = "Connected" if current_keys.get(
            'finnhub_api_key') else "Not Set"
        st.metric("Finnhub", finnhub_status)

    with col3:
        gemini_status = "Connected" if current_keys.get(
            'gemini_api_key') else "Not Set"
        st.metric("Gemini AI", gemini_status)

    st.divider()

    # Alpaca Keys
    with st.expander("Alpaca (Paper Trading)", expanded=not current_keys.get('alpaca_api_key')):
        st.info("""
        **Get your Alpaca Paper Trading keys:**
        1. Go to [Alpaca](https://app.alpaca.markets/)
        2. Sign up/Login → Go to Paper Trading
        3. Click "View" on API Keys → Copy both keys
        """)

        with st.form("alpaca_keys"):
            alpaca_api = st.text_input(
                "API Key",
                value="*" * 10 if current_keys.get('alpaca_api_key') else "",
                type="password"
            )
            alpaca_secret = st.text_input(
                "Secret Key",
                value="*" *
                10 if current_keys.get('alpaca_secret_key') else "",
                type="password"
            )

            if st.form_submit_button("Save Alpaca Keys"):
                if alpaca_api and not alpaca_api.startswith("*"):
                    keys_to_save = {}
                    if alpaca_api:
                        keys_to_save['alpaca_api_key'] = alpaca_api
                    if alpaca_secret:
                        keys_to_save['alpaca_secret_key'] = alpaca_secret

                    if save_user_api_keys(keys_to_save):
                        clear_api_keys_cache()
                        st.success("Alpaca keys saved!")
                        st.rerun()
                    else:
                        st.error("Failed to save keys.")
                else:
                    st.info("No changes to save.")

    # Finnhub Keys
    with st.expander("Finnhub (Real-time Data)", expanded=not current_keys.get('finnhub_api_key')):
        st.info("""
        **Get your free Finnhub API key:**
        1. Go to [Finnhub](https://finnhub.io/)
        2. Sign up for free → Dashboard → API Key
        3. Free tier: 60 calls/minute
        """)

        with st.form("finnhub_keys"):
            finnhub_api = st.text_input(
                "API Key",
                value="*" * 10 if current_keys.get('finnhub_api_key') else "",
                type="password"
            )

            if st.form_submit_button("Save Finnhub Key"):
                if finnhub_api and not finnhub_api.startswith("*"):
                    if save_user_api_keys({'finnhub_api_key': finnhub_api}):
                        clear_api_keys_cache()
                        st.success("Finnhub key saved!")
                        st.rerun()
                    else:
                        st.error("Failed to save key.")
                else:
                    st.info("No changes to save.")

    # Gemini Keys
    with st.expander("Gemini AI (Analysis)", expanded=not current_keys.get('gemini_api_key')):
        st.info("""
        **Get your free Gemini API key:**
        1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
        2. Create API Key → Copy
        3. Free tier: Generous usage limits
        """)

        with st.form("gemini_keys"):
            gemini_api = st.text_input(
                "API Key",
                value="*" * 10 if current_keys.get('gemini_api_key') else "",
                type="password"
            )

            if st.form_submit_button("Save Gemini Key"):
                if gemini_api and not gemini_api.startswith("*"):
                    if save_user_api_keys({'gemini_api_key': gemini_api}):
                        clear_api_keys_cache()
                        st.success("Gemini key saved!")
                        st.rerun()
                    else:
                        st.error("Failed to save key.")
                else:
                    st.info("No changes to save.")

    # Test connection button
    st.divider()
    if st.button("Test All Connections", width='stretch'):
        test_api_connections()


def test_api_connections():
    """Test all API connections."""
    from utils.auth import get_user_decrypted_keys

    keys = get_user_decrypted_keys()

    # Test Alpaca
    st.write("**Testing Alpaca...**")
    if keys.get('alpaca_api_key') and keys.get('alpaca_secret_key'):
        try:
            from alpaca.trading.client import TradingClient
            client = TradingClient(
                keys['alpaca_api_key'],
                keys['alpaca_secret_key'],
                paper=True
            )
            account = client.get_account()
            st.success(
                f"Alpaca connected! Account equity: ${float(account.equity):,.2f}")
        except Exception as e:
            st.error(f"Alpaca error: {e}")
    else:
        st.warning("Alpaca keys not configured")

    # Test Finnhub
    st.write("**Testing Finnhub...**")
    if keys.get('finnhub_api_key'):
        try:
            import finnhub
            client = finnhub.Client(api_key=keys['finnhub_api_key'])
            quote = client.quote("AAPL")
            if quote and quote.get('c', 0) > 0:
                st.success(f"Finnhub connected! AAPL: ${quote['c']:.2f}")
            else:
                st.warning("Finnhub connected but no data returned")
        except Exception as e:
            st.error(f"Finnhub error: {e}")
    else:
        st.warning("Finnhub key not configured")

    # Test Gemini
    st.write("**Testing Gemini...**")
    if keys.get('gemini_api_key'):
        try:
            import google.generativeai as genai
            genai.configure(api_key=keys['gemini_api_key'])
            model = genai.GenerativeModel('gemini-2.0-flash')
            response = model.generate_content("Say 'connected' in one word")
            st.success(f"Gemini connected! Response: {response.text[:50]}...")
        except Exception as e:
            st.error(f"Gemini error: {e}")
    else:
        st.warning("Gemini key not configured")


def render_preferences_settings():
    """Render user preferences section."""
    st.subheader("Preferences")

    from utils.auth import get_current_user_id
    from utils.database import get_user_profile, update_user_profile

    user_id = get_current_user_id()
    if not user_id:
        st.warning("Please log in to access preferences.")
        return

    profile = get_user_profile(user_id) or {}

    with st.form("preferences"):
        starting_capital = st.number_input(
            "Starting Capital ($)",
            min_value=100,
            max_value=1000000,
            value=int(profile.get('starting_capital', 500)),
            step=100,
            help="Used for portfolio calculations"
        )

        risk_profile = st.selectbox(
            "Risk Profile",
            options=["conservative", "moderate", "aggressive"],
            index=["conservative", "moderate", "aggressive"].index(
                profile.get('risk_profile', 'moderate')
            ),
            help="Affects position sizing recommendations"
        )

        if st.form_submit_button("Save Preferences", width='stretch'):
            if update_user_profile(user_id, {
                'starting_capital': starting_capital,
                'risk_profile': risk_profile
            }):
                st.success("Preferences saved!")
            else:
                st.error("Failed to save preferences.")

    # Database info
    st.divider()
    st.caption("Database Status")

    if is_supabase_enabled():
        st.success("Connected to Supabase (Cloud)")
    else:
        st.info("Running in local mode (SQLite)")

    # Export data option
    st.divider()
    if st.button("Export My Data (CSV)"):
        export_user_data(user_id)


# Main entry point when run directly
if __name__ == "__main__":
    render_settings_page()
