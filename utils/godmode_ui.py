"""
GOD MODE UI COMPONENTS
Display all the rich intelligence data from godmode_data.py
"""

import plotly.graph_objects as go  # Required for the Gauge
import streamlit as st
from datetime import datetime
from typing import Dict, Any, List, Optional
import pandas as pd


def render_godmode_sidebar(intelligence: Dict[str, Any]):
    """Renders the Supercharged Sidebar."""

    ticker = intelligence.get("ticker", "N/A")
    data = intelligence

    # 0. Market Status
    status = intelligence.get("market_status")
    if status:
        is_open = status.get("is_open")
        session = str(status.get("session", "")).title()

        if is_open:
            st.sidebar.success(f"🟢 Market Open ({session})")
        else:
            st.sidebar.error(f"🔴 Market Closed")

    # --- 1. LIVE PRICE (Finnhub) ---
    quote = data.get("quote")
    if quote:
        delta = quote["change"]
        color = "normal"  # Standard Red/Green for delta

        st.sidebar.metric(
            f"{ticker} Live Price",
            f"${quote['current']:.2f}",
            f"{delta:+.2f} ({quote['percent_change']:+.2f}%)",
            delta_color=color,
            help="Source: Finnhub Real-Time",
        )
    else:
        st.sidebar.warning("Live price unavailable")

    st.sidebar.divider()

    # --- 2. EARNINGS COUNTDOWN ---
    earn = data.get("earnings")
    if earn:
        st.sidebar.markdown("📅 **Next Earnings**")
        try:
            # 1. Extract Raw Data
            date_str = earn.get("date", "N/A")  # e.g., "2026-02-10"
            quarter = earn.get("quarter", "N/A")
            year = earn.get("year", "N/A")
            eps = earn.get("eps_estimate")

            # 2. Format the Date & Countdown
            display_date = date_str
            countdown_msg = ""

            if date_str and date_str != "N/A":
                from datetime import datetime

                try:
                    # Convert "2026-02-10" to datetime object
                    e_date = datetime.strptime(date_str, "%Y-%m-%d")
                    # Make it pretty: "Feb 10, 2026"
                    display_date = e_date.strftime("%b %d, %Y")

                    # Calculate days remaining
                    delta = (e_date - datetime.now()).days
                    if delta > 0:
                        countdown_msg = f" (in {delta} days)"
                    elif delta == 0:
                        countdown_msg = " 🔥 TODAY"
                    elif delta > -3:
                        countdown_msg = " (Just reported)"
                except:
                    pass  # Fallback to raw string if parsing fails

            # 3. Render
            st.sidebar.write(f"**Q{quarter} {year}**")
            st.sidebar.caption(f"{display_date}{countdown_msg}")

            if eps:
                st.sidebar.caption(f"EPS Est: ${eps:.2f}")

        except Exception as e:
            st.sidebar.caption("Date TBA")
            # print(f"Earnings Error: {e}")

    st.sidebar.divider()

    # --- 3. PEERS ---
    if "peers" in data and data["peers"]:
        st.sidebar.markdown("🔀 **Similar Stocks**")
        peers = data["peers"][:4]
        cols = st.sidebar.columns(len(peers))
        for i, peer in enumerate(peers):
            if cols[i].button(peer, key=f"btn_peer_{peer}"):
                st.session_state["selected_ticker"] = peer
                st.rerun()

    # st.sidebar.divider()

    # --- 4. FUNDAMENTALS ---
    fund = data.get("fundamentals")
    if fund:
        st.sidebar.header(f"🏗️ {ticker} Profile")
        st.sidebar.caption(
            f"**{fund.get('sector', 'N/A')}** | {fund.get('industry', 'N/A')}"
        )

        with st.sidebar.expander("📝 Business Description"):
            st.write(fund.get("summary", "No Data"))

        # Metrics Grid
        c1, c2 = st.sidebar.columns(2)
        with c1:
            val = fund.get("market_cap", 0)
            if isinstance(val, (int, float)) and val > 0:
                if val >= 1e12:
                    s_val = f"${val / 1e12:.2f}T"
                elif val >= 1e9:
                    s_val = f"${val / 1e9:.1f}B"
                else:
                    s_val = f"${val / 1e6:.1f}M"
            else:
                s_val = "N/A"

            st.metric("Market Cap", s_val)

            # P/E Ratio
            pe = fund.get("pe_ratio", "N/A")
            if isinstance(pe, (int, float)) and pe > 0:
                st.metric("P/E Ratio", f"{pe:.2f}")
            else:
                st.metric("P/E Ratio", "N/A")

            # Beta
            beta = fund.get("beta", "N/A")
            if isinstance(beta, (int, float)) and beta != 0:
                st.metric("Beta", f"{beta:.2f}")
            else:
                st.metric("Beta", "N/A")

        with c2:
            # Target Price
            target = fund.get("target_mean", "N/A")
            if isinstance(target, (int, float)) and target > 0:
                st.metric("Target Price", f"${target:.2f}")
            else:
                st.metric("Target Price", "N/A")

            # PEG Ratio
            peg = fund.get("peg_ratio", "N/A")
            if isinstance(peg, (int, float)) and peg > 0:
                st.metric("PEG Ratio", f"{peg:.2f}")
            else:
                st.metric("PEG Ratio", "N/A")

            # Dividend Yield
            div = fund.get("dividend_yield", 0)
            if isinstance(div, (int, float)) and div > 0:
                st.metric("Div Yield", f"{div:.2f}%")
            else:
                st.metric("Div Yield", "None")

        # 52-Week Range
        low = fund.get("year_low", 0)
        high = fund.get("year_high", 0)
        if (
            isinstance(high, (int, float))
            and high > 0
            and isinstance(low, (int, float))
        ):
            st.write("52-Week Range")
            curr = quote.get("current", 0) if quote else 0
            if curr > 0 and (high - low) > 0:
                progress = (curr - low) / (high - low)
                st.progress(min(max(progress, 0.0), 1.0))
            st.caption(f"${low:.2f} — ${high:.2f}")


def render_recommendation_trends(data):
    """
    Renders Analyst Consensus Gauge + Price Target Upside.
    """
    trends = data.get("recommendation_trends")
    targets = data.get("price_targets")
    quote = data.get("quote")

    if not trends or len(trends) == 0:
        st.warning("No analyst data available.")
        return

    st.subheader("🎯 Analyst Consensus")

    # --- 1. CALCULATE SCORE ---
    latest = trends[0]
    s_buy = latest.get("strongBuy", 0)
    buy = latest.get("buy", 0)
    hold = latest.get("hold", 0)
    sell = latest.get("sell", 0)
    s_sell = latest.get("strongSell", 0)

    total = s_buy + buy + hold + sell + s_sell
    if total > 0:
        score = (
            (s_buy * 5) + (buy * 4) + (hold * 3) + (sell * 2) + (s_sell * 1)
        ) / total
    else:
        score = 0

    # Label Logic
    if score >= 4.5:
        label = "STRONG BUY"
    elif score >= 3.5:
        label = "BUY"
    elif score >= 2.5:
        label = "HOLD"
    elif score >= 1.5:
        label = "SELL"
    else:
        label = "STRONG SELL"

    # --- 2. VISUALS ---
    c1, c2 = st.columns([2, 1])

    with c1:
        # GAUGE CHART
        fig = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=score,
                domain={"x": [0, 1], "y": [0, 1]},
                title={
                    "text": f"<b>{label}</b><br><span style='font-size:0.8em;color:gray'>{total} Analysts</span>"
                },
                gauge={
                    "axis": {"range": [1, 5]},
                    "bar": {
                        "color": "#00FF00"
                        if score >= 3.5
                        else "#FFAA00"
                        if score >= 2.5
                        else "#FF0000"
                    },
                    "steps": [
                        {"range": [1, 2.5], "color": "#550000"},
                        {"range": [2.5, 3.5], "color": "#555500"},
                        {"range": [3.5, 5], "color": "#005500"},
                    ],
                    "threshold": {
                        "line": {"color": "white", "width": 4},
                        "thickness": 0.75,
                        "value": score,
                    },
                },
            )
        )
        fig.update_layout(
            height=220,
            margin=dict(l=20, r=20, t=30, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, width="stretch")

    with c2:
        # UPSIDE CARD
        st.markdown("### 💰 Price Target")

        # 1. Try Primary Source (price_targets)
        target_mean = 0
        target_high = 0
        target_low = 0

        if targets:
            target_mean = targets.get("target_mean", 0) or targets.get(
                "targetMedian", 0
            )
            target_high = targets.get("target_high", 0)
            target_low = targets.get("target_low", 0)

        # 2. Try Secondary Source (fundamentals) if Primary failed
        if (not target_mean or target_mean == 0) and data.get("fundamentals"):
            try:
                # Fundamentals might have it as a float or string "150.0"
                t_val = data["fundamentals"].get("target_mean", 0)
                if t_val and t_val != "N/A":
                    target_mean = float(t_val)
            except:
                pass

        # Current Price
        current_price = 0
        if quote:
            current_price = float(quote.get("current", 0))

        # Render
        if target_mean and target_mean > 0 and current_price > 0:
            upside_pct = ((target_mean - current_price) / current_price) * 100

            st.metric("Average Target", f"${target_mean:.2f}")
            st.metric(
                "Implied Upside",
                f"{upside_pct:+.2f}%",
                delta_color="normal" if upside_pct > 0 else "inverse",
            )

            # Only show range if valid
            if target_high > 0 and target_low > 0:
                st.caption(f"Low: ${target_low:.2f} — High: ${target_high:.2f}")
            elif target_high > 0:
                st.caption(f"Target High: ${target_high:.2f}")
        else:
            # Fallback if target is truly missing
            st.info("Target data unavailable")
            st.caption("Consensus is based on ratings only.")

    # Breakdown Grid
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.metric("Strong Buy", s_buy, border=True)
    with k2:
        st.metric("Buy", buy, border=True)
    with k3:
        st.metric("Hold", hold, border=True)
    with k4:
        st.metric("Sell", sell, border=True)
    with k5:
        st.metric("Strong Sell", s_sell, border=True)


def render_news_section(data):
    """Renders News (Verified Links)."""
    # Using Alpca/Benzinga data (raw links)
    news_items = data.get("news")

    st.subheader("📰 Latest News (Verified)")

    if news_items:
        # Simply display the items directly
        count = 0
        for item in news_items:
            if count >= 10:
                break

            # Extract fields safely
            headline = item.get("headline", "No Headline")
            url = item.get("url", "#")
            source = item.get("author", "News Source")
            time = str(item.get("created_at", ""))[:10]  # Just the date

            # Render as a clean card
            st.markdown(f"**[{headline}]({url})**")
            st.caption(f"_{source} • {time}_")
            st.divider()
            count += 1
    else:
        st.warning("No real-time news found. Check external sources.")


def render_insider_section(data):
    """Renders the Insider Trading Table."""
    st.subheader("🕵️ Insider Activity (Last 3 Months)")

    insiders = data.get("insiders")
    if not insiders:
        st.info("No recent insider activity reported.")
        return

    buy_vol = 0
    sell_vol = 0
    clean_trades = []

    for t in insiders:
        shares = t.get("share", 0)
        price = t.get("transactionPrice", 0)
        val = shares * price
        change = t.get("change", 0)

        if change > 0:
            buy_vol += val
            action = "BUY 🟢"
        else:
            sell_vol += val
            action = "SELL 🔴"

        clean_trades.append(
            {
                "Date": t.get("transactionDate"),
                "Insider": t.get("name"),
                "Action": action,
                "Shares": f"{abs(change):,}",
                "Price": f"${price:.2f}",
                "Value": f"${abs(val):,.0f}",
            }
        )

    c1, c2 = st.columns(2)
    c1.metric("Total Buys", f"${buy_vol:,.0f}")
    c2.metric("Total Sells", f"${sell_vol:,.0f}")

    if sell_vol > buy_vol:
        st.error("🔴 Net Insider Selling")
    elif buy_vol > sell_vol:
        st.success("🟢 Net Insider Buying")

    st.dataframe(clean_trades, width="stretch")


def render_price_targets(targets, current):
    # Backward compatibility stub
    pass


def render_earnings_widget(earnings):
    # Backward compatibility stub - logic moved to sidebar renderer
    pass


def render_performance_chart(df):
    """
    Renders an Equity Curve using Plotly.
    """
    if df is None or df.empty:
        st.info("No performance history available yet.")
        return

    import plotly.graph_objects as go

    # Determine Color (Green if profitable, Red if loss)
    start_equity = df["equity"].iloc[0]
    end_equity = df["equity"].iloc[-1]
    color = "#00FF00" if end_equity >= start_equity else "#FF0000"

    # Calculate Total Return
    total_return = end_equity - start_equity
    total_pct = (total_return / start_equity) * 100 if start_equity > 0 else 0

    st.subheader("📈 Account Performance")

    # Scorecard
    c1, c2, c3 = st.columns(3)
    c1.metric("Start Equity", f"${start_equity:,.2f}")
    c2.metric("Current Equity", f"${end_equity:,.2f}")
    # Use more precision for small percentages
    pct_fmt = f"{total_pct:+.4f}%" if abs(total_pct) < 1 else f"{total_pct:+.2f}%"
    c3.metric("Net Profit", f"${total_return:+,.2f}", pct_fmt)

    # Calculate dynamic y-axis range (like Price Action chart)
    val_min = float(df["equity"].min())
    val_max = float(df["equity"].max())
    val_range = val_max - val_min
    if val_range < 1:  # Handle flat values
        val_range = val_max * 0.02
    y_padding = val_range * 0.1
    y_min = val_min - y_padding
    y_max = val_max + y_padding

    # Determine fill color
    if end_equity >= start_equity:
        fill_color = "rgba(0, 255, 0, 0.15)"
    else:
        fill_color = "rgba(255, 0, 0, 0.15)"

    # The Chart
    fig = go.Figure()

    # Area Chart for Equity
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["equity"],
            mode="lines",
            name="Equity",
            line=dict(color=color, width=2),
            fill="tozeroy",
            fillcolor=fill_color,
            hovertemplate="%{x}<br>$%{y:,.2f}<extra></extra>",
        )
    )

    fig.update_layout(
        height=350,
        margin=dict(l=0, r=0, t=20, b=0),
        xaxis=dict(showgrid=False),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(128,128,128,0.2)",
            tickprefix="$",
            range=[y_min, y_max],  # Dynamic range
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
    )

    st.plotly_chart(fig, width="stretch")
