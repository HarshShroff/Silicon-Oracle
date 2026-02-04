"""
Silicon Oracle - Email Notifications Service
BYOK: Users send from their own Gmail address using App Passwords.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# ============================================
# EMAIL SENDING (Gmail SMTP)
# ============================================


def send_email(
    to_email: str,
    subject: str,
    body_html: str,
    from_email: Optional[str] = None,
    app_password: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send an email via Gmail SMTP.

    BYOK Mode: If from_email and app_password are provided, sends from user's Gmail.
    Otherwise, attempts to use app config (system fallback).

    Returns: {"success": True} or {"success": False, "error": "..."}
    """
    # Get credentials
    sender = from_email
    password = app_password

    if not sender or not password:
        # Try to get from app config
        try:
            from flask import current_app

            sender = current_app.config.get("GMAIL_ADDRESS")
            password = current_app.config.get("GMAIL_APP_PASSWORD")
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
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender, password)
            server.send_message(msg)

        return {"success": True}

    except smtplib.SMTPAuthenticationError:
        logger.error(f"Gmail Auth Failed for {sender}. Check App Password.")
        return {
            "success": False,
            "error": "Gmail authentication failed. Check your App Password.",
        }
    except Exception as e:
        logger.error(f"Email send error to {to_email} via {sender}: {e}")
        return {"success": False, "error": f"Email error: {str(e)}"}


def send_self_notification(
    user_email: str, app_password: str, subject: str, body_html: str
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
        app_password=app_password,
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
                background-color: #f4f4f4;
            }}
            .header {{
                background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #22d3ee 100%);
                color: white;
                padding: 20px;
                border-radius: 8px;
                text-align: center;
                margin-bottom: 30px;
            }}
            .content {{
                background: white;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .metric {{
                display: inline-block;
                margin: 10px 0;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
            }}
            .positive {{
                background-color: #10b981;
                color: white;
            }}
            .negative {{
                background-color: #ef4444;
                color: white;
            }}
            .footer {{
                text-align: center;
                margin-top: 30px;
                color: #666;
                font-size: 14px;
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
            <p>Sent by Silicon Oracle - AI-Powered Stock Analysis</p>
            <p>{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        </div>
    </body>
    </html>
    """


def price_alert_email(ticker: str, current_price: float, target_price: float) -> str:
    """Generate price alert email content."""
    change_pct = ((current_price - target_price) / target_price) * 100

    content = f"""
        <h2>🎯 Price Alert: {ticker}</h2>
        <p>Target price has been reached!</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <div style="font-size: 24px; margin-bottom: 10px;">
                <strong>{ticker}</strong>: ${current_price:.2f}
            </div>
            <div class="metric {"positive" if change_pct >= 0 else "negative"}">
                {change_pct:+.2f}% from target
            </div>
        </div>
        
        <p>Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    """

    return get_base_template(content, "Price Alert")


def ai_signal_email(ticker: str, verdict: str, score: float, reasons: List[str]) -> str:
    """Generate AI signal email content."""
    score_color = "positive" if score >= 8 else "negative" if score <= 4 else ""

    content = f"""
        <h2>🤖 AI Signal Alert: {ticker}</h2>
        <p>The Oracle has identified a trading opportunity!</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <div class="metric {score_color}">
                Oracle Score: {score:.1f}/12
            </div>
            <div style="font-size: 20px; margin-top: 10px;">
                <strong>Verdict: {verdict}</strong>
            </div>
        </div>
        
        <h3>Top Reasons:</h3>
        <ul>
            {"<li>" + "</li><li>".join(reasons[:3]) + "</li>" if reasons else "<li>No specific reasons</li>"}
        </ul>
        
        <p>Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    """

    return get_base_template(content, "AI Signal Alert")


def position_alert_email(
    ticker: str, action: str, pnl_amount: float, pnl_percent: float
) -> str:
    """Generate position alert email content."""
    action_type = (
        "Stop Loss"
        if pnl_percent < -10
        else "Take Profit"
        if pnl_percent > 20
        else "Position Update"
    )
    pnl_class = "negative" if pnl_amount < 0 else "positive"

    content = f"""
        <h2>📊 {action_type}: {ticker}</h2>
        <p>Position alert for your {ticker} position</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <div class="metric {pnl_class}">
                P&L: ${pnl_amount:+.2f}
            </div>
            <div class="metric {pnl_class}">
                {pnl_percent:+.2f}%
            </div>
        </div>
        
        <p>Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    """

    return get_base_template(content, f"{action_type} Alert")


def daily_digest_email(
    portfolio_summary: Dict, top_opportunities: List[Dict], market_status: Dict,
    holdings: List[Dict] = None
) -> str:
    """Generate daily digest email content."""
    total_value = portfolio_summary.get("total_value", 0)
    portfolio_value = portfolio_summary.get("portfolio_value", total_value)
    cash = portfolio_summary.get("cash", 0)
    days_pnl = portfolio_summary.get("days_pnl", 0)
    days_pnl_pct = portfolio_summary.get("days_pnl_percent", 0)
    pnl_class = "positive" if days_pnl >= 0 else "negative"

    # Shadow portfolio holdings table
    holdings_html = ""
    if holdings:
        for h in holdings:
            h_pnl_class = "positive" if h.get('pnl', 0) >= 0 else "negative"
            holdings_html += f"""
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>{h.get('ticker', '')}</strong></td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">{h.get('shares', 0):.2f}</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">${h.get('price', 0):.2f}</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">${h.get('market_value', 0):,.2f}</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">
                    <span class="metric {h_pnl_class}">${h.get('pnl', 0):+,.2f} ({h.get('pnl_pct', 0):+.1f}%)</span>
                </td>
            </tr>
            """

    opportunities_html = ""
    for opp in top_opportunities[:5]:
        ticker = opp.get("ticker", "")
        score = opp.get("oracle_score", 0)
        verdict = opp.get("verdict", "")

        opp_color = "positive" if score >= 8 else "negative" if score <= 4 else ""
        opportunities_html += f"""
        <tr>
            <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>{ticker}</strong></td>
            <td style="padding: 10px; border-bottom: 1px solid #eee;">${opp.get("price", 0):.2f}</td>
            <td style="padding: 10px; border-bottom: 1px solid #eee;">
                <span class="metric {opp_color}">{score:.1f}</span>
            </td>
            <td style="padding: 10px; border-bottom: 1px solid #eee;">{verdict}</td>
        </tr>
        """

    market_signal = "📈 Risk-On" if market_status.get(
        "is_healthy") else "📉 Risk-Off"

    content = f"""
        <h2>📈 Silicon Oracle Daily Digest</h2>
        <p>Shadow Portfolio Summary for {datetime.now().strftime("%B %d, %Y")}</p>

        <h3>Portfolio Summary</h3>
        <div style="text-align: center; margin: 30px 0;">
            <div class="metric">
                Total Equity: ${total_value:,.2f}
            </div>
            <div style="display: flex; justify-content: center; gap: 40px; margin-top: 10px;">
                <div class="metric" style="font-size: 14px;">Positions: ${portfolio_value:,.2f}</div>
                <div class="metric" style="font-size: 14px;">Cash: ${cash:,.2f}</div>
            </div>
            <div class="metric {pnl_class}" style="margin-top: 15px;">
                P&L: ${days_pnl:+,.2f} ({days_pnl_pct:+.2f}%)
            </div>
        </div>

        <h3>Market Status</h3>
        <div style="text-align: center; margin: 20px 0; font-size: 18px;">
            {market_signal}
        </div>

        <h3>💼 Shadow Portfolio Holdings</h3>
        {f'''<table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
            <thead><tr style="background-color: #f8f9fa;">
                <th style="padding: 10px; text-align: left;">Ticker</th>
                <th style="padding: 10px; text-align: right;">Shares</th>
                <th style="padding: 10px; text-align: right;">Price</th>
                <th style="padding: 10px; text-align: right;">Value</th>
                <th style="padding: 10px; text-align: right;">P&L</th>
            </tr></thead>
            <tbody>{holdings_html}</tbody>
        </table>''' if holdings_html else '<p style="color: #888; font-size: 14px;">No shadow positions yet. Portfolio Sentinel will add positions automatically when it detects opportunities.</p>'}

        <h3>🎯 Top Opportunities</h3>
        {f'''<table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
            <thead><tr style="background-color: #f8f9fa;">
                <th style="padding: 10px; text-align: left;">Ticker</th>
                <th style="padding: 10px; text-align: right;">Price</th>
                <th style="padding: 10px; text-align: center;">Score</th>
                <th style="padding: 10px; text-align: left;">Verdict</th>
            </tr></thead>
            <tbody>{opportunities_html}</tbody>
        </table>''' if opportunities_html else '<p style="color: #888; font-size: 14px;">Run a market scan to populate top opportunities.</p>'}

        <p><em>This is an automated daily digest for your shadow portfolio. Configure alerts in Settings.</em></p>
    """

    return get_base_template(content, "Daily Digest")


# ============================================
# NOTIFICATION FUNCTIONS
# ============================================


def send_price_alert(
    user_email: str,
    app_password: str,
    ticker: str,
    current_price: float,
    target_price: float,
) -> Dict[str, Any]:
    """Send price alert notification."""
    if not user_email or not app_password:
        return {"success": False, "error": "Email credentials not configured"}

    body_html = price_alert_email(ticker, current_price, target_price)
    return send_self_notification(
        user_email, app_password, f"{ticker} Price Alert", body_html
    )


def send_ai_signal_alert(
    user_email: str,
    app_password: str,
    ticker: str,
    verdict: str,
    score: float,
    reasons: List[str],
) -> Dict[str, Any]:
    """Send AI signal alert notification."""
    if not user_email or not app_password:
        return {"success": False, "error": "Email credentials not configured"}

    body_html = ai_signal_email(ticker, verdict, score, reasons)
    return send_self_notification(
        user_email, app_password, f"AI Signal: {ticker}", body_html
    )


def send_position_alert(
    user_email: str,
    app_password: str,
    ticker: str,
    action: str,
    pnl_amount: float,
    pnl_percent: float,
) -> Dict[str, Any]:
    """Send position alert notification."""
    if not user_email or not app_password:
        return {"success": False, "error": "Email credentials not configured"}

    body_html = position_alert_email(ticker, action, pnl_amount, pnl_percent)
    return send_self_notification(
        user_email, app_password, f"{action}: {ticker}", body_html
    )


def send_daily_digest(
    target_email: str,
    app_password: str,
    portfolio_summary: Dict,
    top_opportunities: List[Dict],
    market_status: Dict,
    sender_email: Optional[str] = None,
    holdings: List[Dict] = None,
) -> Dict[str, Any]:
    """Send daily digest notification."""
    if not target_email or not app_password:
        return {"success": False, "error": "Email credentials not configured"}

    body_html = daily_digest_email(
        portfolio_summary, top_opportunities, market_status, holdings=holdings)
    return send_email(
        target_email,
        "Daily Digest - Shadow Portfolio",
        body_html,
        from_email=sender_email or target_email,
        app_password=app_password
    )


# ============================================
# TEST FUNCTIONS
# ============================================


def test_email_config(user_email: str, app_password: str) -> Dict[str, Any]:
    """Test email configuration by sending a test email."""
    if not user_email or not app_password:
        return {"success": False, "error": "Email credentials not provided"}

    content = f"""
        <h2>✅ Email Test Successful</h2>
        <p>Your Silicon Oracle email configuration is working correctly!</p>
        <p>This is a test email to verify your Gmail App Password is working.</p>
        <p>Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    """

    body_html = get_base_template(content, "Test Email")

    return send_self_notification(
        user_email, app_password, "Test Successful", body_html
    )
