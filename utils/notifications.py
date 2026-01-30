"""
Email Notifications for Silicon Oracle.
BYOK: Users send from their own Gmail address using App Passwords.
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any, List
from datetime import datetime
import streamlit as st


# ============================================
# EMAIL SENDING (Gmail SMTP)
# ============================================

def send_email(
    to_email: str,
    subject: str,
    body_html: str,
    from_email: Optional[str] = None,
    app_password: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send an email via Gmail SMTP.

    BYOK Mode: If from_email and app_password are provided, sends from user's Gmail.
    Otherwise, attempts to use secrets (for system emails).

    Returns: {"success": True} or {"success": False, "error": "..."}
    """
    # Get credentials
    sender = from_email
    password = app_password

    if not sender or not password:
        # Try to get from secrets (system fallback)
        try:
            sender = st.secrets.get("gmail", {}).get("address")
            password = st.secrets.get("gmail", {}).get("app_password")
        except Exception:
            pass

    if not sender or not password:
        return {"success": False, "error": "No email credentials configured."}

    try:
        # Create message
        msg = MIMEMultipart("alternative")
        msg["From"] = sender
        msg["To"] = to_email
        msg["Subject"] = f"Silicon Oracle: {subject}"

        # Add HTML body
        msg.attach(MIMEText(body_html, "html"))

        # Send via Gmail SMTP
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.send_message(msg)

        return {"success": True}

    except smtplib.SMTPAuthenticationError:
        return {"success": False, "error": "Gmail authentication failed. Check your App Password."}
    except Exception as e:
        return {"success": False, "error": f"Email error: {str(e)}"}


def send_self_notification(
    user_email: str,
    app_password: str,
    subject: str,
    body_html: str
) -> Dict[str, Any]:
    """
    Send notification email to user's own email (BYOK style).
    User sends to themselves from their own Gmail.
    """
    return send_email(
        to_email=user_email,
        subject=subject,
        body_html=body_html,
        from_email=user_email,
        app_password=app_password
    )


# ============================================
# EMAIL TEMPLATES
# ============================================

def get_base_template(content: str, title: str = "Silicon Oracle") -> str:
    """Base HTML email template."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background: linear-gradient(135deg, #6C63FF 0%, #4834d4 100%);
                color: white;
                padding: 20px;
                border-radius: 10px 10px 0 0;
                text-align: center;
            }}
            .content {{
                background: #f8f9fa;
                padding: 20px;
                border-radius: 0 0 10px 10px;
            }}
            .ticker {{
                font-size: 24px;
                font-weight: bold;
                color: #6C63FF;
            }}
            .buy {{ color: #00C853; }}
            .sell {{ color: #FF5252; }}
            .hold {{ color: #FFB300; }}
            .metric {{
                display: inline-block;
                margin: 10px;
                padding: 10px;
                background: white;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .footer {{
                margin-top: 20px;
                text-align: center;
                font-size: 12px;
                color: #888;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>{title}</h1>
        </div>
        <div class="content">
            {content}
        </div>
        <div class="footer">
            Sent by Silicon Oracle | AI-Powered Trading Assistant
        </div>
    </body>
    </html>
    """


def format_price_alert(ticker: str, current_price: float, target_price: float, direction: str) -> str:
    """Format price alert email."""
    content = f"""
    <h2>Price Alert: <span class="ticker">{ticker}</span></h2>
    <p>Your price target has been hit!</p>
    <div class="metric">
        <strong>Current Price:</strong> ${current_price:.2f}
    </div>
    <div class="metric">
        <strong>Target Price:</strong> ${target_price:.2f}
    </div>
    <p>Direction: <strong>{direction}</strong></p>
    <p><em>Alert triggered at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>
    """
    return get_base_template(content, "Price Alert")


def format_ai_signal(ticker: str, verdict: str, score: float, reasons: List[str]) -> str:
    """Format AI signal/recommendation email."""
    verdict_class = verdict.lower().replace(" ", "-")
    if "buy" in verdict.lower():
        verdict_class = "buy"
    elif "sell" in verdict.lower() or "avoid" in verdict.lower():
        verdict_class = "sell"
    else:
        verdict_class = "hold"

    reasons_html = "".join([f"<li>{r}</li>" for r in reasons[:3]])

    content = f"""
    <h2>AI Signal: <span class="ticker">{ticker}</span></h2>
    <div class="metric">
        <strong>Verdict:</strong> <span class="{verdict_class}">{verdict}</span>
    </div>
    <div class="metric">
        <strong>Oracle Score:</strong> {score:.1f}/12.0
    </div>
    <h3>Key Reasons:</h3>
    <ul>
        {reasons_html}
    </ul>
    <p><em>Scanned at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>
    """
    return get_base_template(content, "AI Signal")


def format_position_alert(
    ticker: str,
    alert_type: str,
    entry_price: float,
    current_price: float,
    pnl_pct: float
) -> str:
    """Format position alert (stop-loss/take-profit)."""
    pnl_class = "buy" if pnl_pct >= 0 else "sell"

    content = f"""
    <h2>Position Alert: <span class="ticker">{ticker}</span></h2>
    <p><strong>{alert_type}</strong></p>
    <div class="metric">
        <strong>Entry Price:</strong> ${entry_price:.2f}
    </div>
    <div class="metric">
        <strong>Current Price:</strong> ${current_price:.2f}
    </div>
    <div class="metric">
        <strong>P&L:</strong> <span class="{pnl_class}">{pnl_pct:+.2f}%</span>
    </div>
    <p><em>Alert triggered at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>
    """
    return get_base_template(content, "Position Alert")


def format_daily_digest(picks: List[Dict[str, Any]], account_summary: Dict[str, Any]) -> str:
    """Format daily digest email."""
    picks_html = ""
    for pick in picks[:5]:
        verdict_class = "buy" if "buy" in pick.get(
            "verdict", "").lower() else "hold"
        picks_html += f"""
        <div class="metric" style="width: 100%; margin: 5px 0;">
            <strong>{pick['ticker']}</strong> -
            <span class="{verdict_class}">{pick.get('verdict', 'N/A')}</span>
            (Score: {pick.get('score', 0):.1f})
        </div>
        """

    content = f"""
    <h2>Daily Digest</h2>
    <p>Here's your morning briefing from Silicon Oracle.</p>

    <h3>Account Summary</h3>
    <div class="metric">
        <strong>Portfolio Value:</strong> ${account_summary.get('portfolio_value', 0):,.2f}
    </div>
    <div class="metric">
        <strong>Buying Power:</strong> ${account_summary.get('buying_power', 0):,.2f}
    </div>
    <div class="metric">
        <strong>Daily Change:</strong> {account_summary.get('daily_change', 0):+.2f}%
    </div>

    <h3>Top Picks Today</h3>
    {picks_html if picks_html else "<p>No strong signals today.</p>"}

    <p><em>Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>
    """
    return get_base_template(content, "Daily Digest")


def format_test_email() -> str:
    """Format test email."""
    content = """
    <h2>Test Email</h2>
    <p>If you're reading this, your email notifications are working correctly!</p>
    <p>You'll receive alerts for:</p>
    <ul>
        <li>Price targets being hit</li>
        <li>AI signals (Strong Buy recommendations)</li>
        <li>Position alerts (stop-loss/take-profit)</li>
        <li>Daily market digest</li>
    </ul>
    <p>You can configure these in the Settings tab.</p>
    """
    return get_base_template(content, "Test Email")


# ============================================
# NOTIFICATION TRIGGERS
# ============================================

def send_price_alert(user_email: str, app_password: str, ticker: str,
                     current_price: float, target_price: float, direction: str) -> Dict[str, Any]:
    """Send price alert notification."""
    body = format_price_alert(ticker, current_price, target_price, direction)
    return send_self_notification(user_email, app_password, f"Price Alert: {ticker}", body)


def send_ai_signal(user_email: str, app_password: str, ticker: str,
                   verdict: str, score: float, reasons: List[str]) -> Dict[str, Any]:
    """Send AI signal notification."""
    body = format_ai_signal(ticker, verdict, score, reasons)
    return send_self_notification(user_email, app_password, f"AI Signal: {ticker} - {verdict}", body)


def send_position_alert(user_email: str, app_password: str, ticker: str,
                        alert_type: str, entry_price: float, current_price: float,
                        pnl_pct: float) -> Dict[str, Any]:
    """Send position alert notification."""
    body = format_position_alert(
        ticker, alert_type, entry_price, current_price, pnl_pct)
    return send_self_notification(user_email, app_password, f"Position Alert: {ticker}", body)


def send_daily_digest(user_email: str, app_password: str,
                      picks: List[Dict[str, Any]], account_summary: Dict[str, Any]) -> Dict[str, Any]:
    """Send daily digest notification."""
    body = format_daily_digest(picks, account_summary)
    return send_self_notification(user_email, app_password, "Daily Digest", body)


def send_test_notification(user_email: str, app_password: str) -> Dict[str, Any]:
    """Send test notification to verify setup."""
    body = format_test_email()
    return send_self_notification(user_email, app_password, "Test Notification", body)


# ============================================
# NOTIFICATION SETTINGS UI
# ============================================

def render_notification_settings():
    """Render notification settings in Streamlit."""
    st.subheader("Email Notifications")
    st.caption("Receive alerts from your own Gmail (BYOK)")

    # Get current user's settings
    from utils.auth import get_current_user_id, get_user_decrypted_keys, save_user_api_keys
    from utils.database import get_user_profile, update_user_profile

    user_id = get_current_user_id()
    if not user_id:
        st.warning("Please log in to configure notifications.")
        return

    profile = get_user_profile(user_id)
    keys = get_user_decrypted_keys()

    # Current status
    enabled = profile.get("notifications_enabled", False) if profile else False
    gmail = keys.get("gmail_address") or (
        profile.get("gmail_address") if profile else "")

    st.write("**Status:**", "Enabled" if enabled and gmail else "Disabled")

    with st.expander("Configure Email Settings", expanded=not gmail):
        st.info("""
        **How to set up Gmail App Password:**
        1. Go to [Google Account Security](https://myaccount.google.com/security)
        2. Enable 2-Factor Authentication (if not already)
        3. Search for "App passwords" → Create new app password
        4. Copy the 16-character password and paste below
        """)

        with st.form("notification_settings"):
            new_gmail = st.text_input("Gmail Address", value=gmail or "")
            new_app_password = st.text_input(
                "App Password",
                type="password",
                placeholder="xxxx xxxx xxxx xxxx",
                help="16-character app password from Google"
            )

            col1, col2 = st.columns(2)
            with col1:
                enable_notifications = st.checkbox(
                    "Enable Notifications", value=enabled)
            with col2:
                test_btn = st.form_submit_button("Send Test Email")

            save_btn = st.form_submit_button("Save Settings", width='stretch')

            if save_btn:
                # Save to database
                updates = {
                    "gmail_address": new_gmail,
                    "notifications_enabled": enable_notifications
                }
                if new_app_password:
                    # Encrypt and save the app password
                    from utils.encryption import encrypt_value
                    updates["gmail_app_password_encrypted"] = encrypt_value(
                        new_app_password)

                if update_user_profile(user_id, updates):
                    st.success("Settings saved!")
                    st.rerun()
                else:
                    st.error("Failed to save settings.")

            if test_btn:
                if not new_gmail:
                    st.error("Please enter your Gmail address.")
                elif not new_app_password and not keys.get("gmail_app_password"):
                    st.error("Please enter your App Password.")
                else:
                    pwd = new_app_password or keys.get(
                        "gmail_app_password", "")
                    result = send_test_notification(new_gmail, pwd)
                    if result["success"]:
                        st.success("Test email sent! Check your inbox.")
                    else:
                        st.error(result["error"])

    # Alert preferences
    if enabled and gmail:
        st.write("**Alert Types:**")

        # Get current alert preferences from profile
        alert_prefs = {
            'price_alerts': profile.get('alert_price', True) if profile else True,
            'ai_signals': profile.get('alert_ai_signals', True) if profile else True,
            'position_alerts': profile.get('alert_positions', True) if profile else True,
            'daily_digest': profile.get('alert_daily_digest', False) if profile else False,
        }

        with st.form("alert_preferences"):
            col1, col2 = st.columns(2)
            with col1:
                price_alerts = st.checkbox("Price alerts", value=alert_prefs['price_alerts'],
                                          help="Get notified when stocks hit your price targets")
                ai_signals = st.checkbox("AI signals (Strong Buy)", value=alert_prefs['ai_signals'],
                                        help="Get notified when Oracle finds strong buy signals")
            with col2:
                position_alerts = st.checkbox("Position alerts", value=alert_prefs['position_alerts'],
                                             help="Get stop-loss and take-profit alerts")
                daily_digest = st.checkbox("Daily digest (6 AM)", value=alert_prefs['daily_digest'],
                                          help="Receive a daily summary of your portfolio")

            if st.form_submit_button("Save Alert Preferences", width='stretch'):
                alert_updates = {
                    'alert_price': price_alerts,
                    'alert_ai_signals': ai_signals,
                    'alert_positions': position_alerts,
                    'alert_daily_digest': daily_digest,
                }
                if update_user_profile(user_id, alert_updates):
                    st.success("Alert preferences saved!")
                    st.rerun()
                else:
                    st.error("Failed to save alert preferences.")
