"""
Silicon Oracle - Email Notification Service
Sends alerts and notifications to users via email (Gmail SMTP or SendGrid API)
"""

import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending email notifications."""

    def __init__(self, config: Optional[Dict[str, str]] = None):
        self.config = config or {}
        self.gmail_address: Optional[str] = self.config.get("gmail_address")
        self.gmail_app_password: Optional[str] = self.config.get("gmail_app_password")
        self.base_url = self.config.get("base_url", "http://localhost:5000")  # Default
        self.enabled = bool(self.gmail_address and self.gmail_app_password)

    def is_configured(self) -> bool:
        """Check if email service is properly configured."""
        return self.enabled

    def send_email(
        self, to_email: str, subject: str, html_body: str, text_body: Optional[str] = None
    ) -> bool:
        """Send an email via Gmail SMTP."""
        if not self.enabled:
            logger.warning("Email service not configured. Skipping notification.")
            return False

        return self._send_via_gmail_smtp(to_email, subject, html_body, text_body)

    def _send_via_gmail_smtp(
        self, to_email: str, subject: str, html_body: str, text_body: Optional[str] = None
    ) -> bool:
        """Send email via Gmail SMTP (tries port 465 SSL, then 587 STARTTLS)."""
        if not self.gmail_address or not self.gmail_app_password:
            return False
        gmail_address: str = self.gmail_address
        gmail_app_password: str = self.gmail_app_password
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Silicon Oracle <{gmail_address}>"
        msg["To"] = to_email

        # Plain text fallback
        if text_body:
            part1 = MIMEText(text_body, "plain")
            msg.attach(part1)

        # HTML content
        part2 = MIMEText(html_body, "html")
        msg.attach(part2)

        # Try port 465 with SSL first (may work on cloud platforms that block 587)
        try:
            logger.info(f"Attempting to send email to {to_email} via Gmail SMTP SSL (port 465)...")
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.ehlo()
                server.login(gmail_address, gmail_app_password)
                server.sendmail(gmail_address, to_email, msg.as_string())

            logger.info(f"Email sent successfully to {to_email} via Gmail SMTP SSL")
            return True

        except Exception as e_ssl:
            logger.warning(f"Gmail SMTP SSL (465) failed: {e_ssl}. Trying STARTTLS (587)...")

            # Fallback to port 587 with STARTTLS (works locally)
            try:
                logger.info(
                    f"Attempting to send email to {to_email} via Gmail SMTP STARTTLS (port 587)..."
                )
                with smtplib.SMTP("smtp.gmail.com", 587) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(gmail_address, gmail_app_password)
                    server.sendmail(gmail_address, to_email, msg.as_string())

                logger.info(f"Email sent successfully to {to_email} via Gmail SMTP STARTTLS")
                return True

            except smtplib.SMTPAuthenticationError:
                logger.error(f"Gmail Auth Failed for {gmail_address}. Check App Password.")
                return False
            except Exception as e_starttls:
                logger.error(
                    f"Both Gmail SMTP methods failed. SSL (465): {e_ssl}, STARTTLS (587): {e_starttls}"
                )
                return False

    def send_alert_notification(
        self,
        to_email: str,
        alerts: List[Dict[str, Any]],
        portfolio_summary: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Send portfolio alert notification."""
        if not alerts:
            return False

        subject = f"🚨 Silicon Oracle Alert: {len(alerts)} Action(s) Required"

        # Build HTML email
        html_body = self._build_alert_email_html(alerts, portfolio_summary)
        text_body = self._build_alert_email_text(alerts, portfolio_summary)

        return self.send_email(to_email, subject, html_body, text_body)

    def send_daily_digest(
        self,
        to_email: str,
        positions: List[Dict[str, Any]],
        news_items: List[Dict[str, Any]],
        portfolio_summary: Dict[str, Any],
    ) -> bool:
        """Send daily portfolio digest."""
        subject = f"📊 Silicon Oracle Daily Digest - {datetime.now().strftime('%b %d, %Y')}"

        html_body = self._build_digest_email_html(positions, news_items, portfolio_summary)
        text_body = self._build_digest_email_text(positions, news_items, portfolio_summary)

        return self.send_email(to_email, subject, html_body, text_body)

    def send_price_alert(
        self,
        to_email: str,
        ticker: str,
        alert_type: str,
        current_price: float,
        trigger_price: float,
        change_percent: float,
    ) -> bool:
        """Send price movement alert."""
        direction = "📈" if change_percent > 0 else "📉"
        subject = f"{direction} {ticker} Price Alert: {change_percent:+.2f}%"

        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #0f172a; color: #e2e8f0; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #1e293b; border-radius: 12px; padding: 24px;">
                <h1 style="color: {'#22c55e' if change_percent > 0 else '#ef4444'}; margin-bottom: 16px;">
                    {direction} {ticker} Price Alert
                </h1>
                <div style="background-color: #334155; padding: 16px; border-radius: 8px; margin-bottom: 16px;">
                    <p style="margin: 0; font-size: 14px; color: #94a3b8;">Alert Type</p>
                    <p style="margin: 4px 0 0 0; font-size: 18px; font-weight: bold;">{alert_type}</p>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                    <div style="background-color: #334155; padding: 12px; border-radius: 8px;">
                        <p style="margin: 0; font-size: 12px; color: #94a3b8;">Current Price</p>
                        <p style="margin: 4px 0 0 0; font-size: 20px; font-weight: bold;">${current_price:.2f}</p>
                    </div>
                    <div style="background-color: #334155; padding: 12px; border-radius: 8px;">
                        <p style="margin: 0; font-size: 12px; color: #94a3b8;">Change</p>
                        <p style="margin: 4px 0 0 0; font-size: 20px; font-weight: bold; color: {'#22c55e' if change_percent > 0 else '#ef4444'};">
                            {change_percent:+.2f}%
                        </p>
                    </div>
                </div>
                <div style="margin-top: 20px; text-align: center;">
                    <a href="{self.base_url}/trade/{ticker}"
                       style="background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold;">
                        View Full Analysis
                    </a>
                </div>
                <p style="margin-top: 24px; font-size: 12px; color: #64748b; text-align: center;">
                    Silicon Oracle - AI-Powered Stock Monitoring
                </p>
            </div>
        </body>
        </html>
        """

        text_body = f"""
{ticker} Price Alert

Alert Type: {alert_type}
Current Price: ${current_price:.2f}
Change: {change_percent:+.2f}%

View full analysis at your Silicon Oracle dashboard.
        """

        return self.send_email(to_email, subject, html_body, text_body)

    def send_news_alert(self, to_email: str, ticker: str, news_item: Dict[str, Any]) -> bool:
        """Send breaking news alert for a holding."""
        subject = f"📰 News Alert: {ticker} - {news_item.get('headline', 'Breaking News')[:50]}..."

        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #0f172a; color: #e2e8f0; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #1e293b; border-radius: 12px; padding: 24px;">
                <h1 style="color: #6366f1; margin-bottom: 16px;">📰 {ticker} News Alert</h1>
                <div style="background-color: #334155; padding: 16px; border-radius: 8px; margin-bottom: 16px;">
                    <h2 style="margin: 0 0 8px 0; font-size: 18px; color: white;">
                        {news_item.get('headline', 'Breaking News')}
                    </h2>
                    <p style="margin: 0; font-size: 12px; color: #94a3b8;">
                        Source: {news_item.get('source', 'Unknown')} |
                        {news_item.get('published', 'Recently')}
                    </p>
                </div>
                <div style="text-align: center;">
                    <a href="{news_item.get('url', '#')}"
                       style="background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold;">
                        Read Full Article
                    </a>
                </div>
                <p style="margin-top: 24px; font-size: 12px; color: #64748b; text-align: center;">
                    Silicon Oracle - AI-Powered Stock Monitoring
                </p>
            </div>
        </body>
        </html>
        """

        text_body = f"""
{ticker} News Alert

{news_item.get('headline', 'Breaking News')}

Source: {news_item.get('source', 'Unknown')}
Published: {news_item.get('published', 'Recently')}

Read more: {news_item.get('url', '')}
        """

        return self.send_email(to_email, subject, html_body, text_body)

    def _build_alert_email_html(
        self, alerts: List[Dict[str, Any]], portfolio_summary: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build HTML for alert notification email."""
        alert_rows = ""
        for alert in alerts:
            priority_color = {
                "CRITICAL": "#ef4444",
                "HIGH": "#f97316",
                "MEDIUM": "#eab308",
                "LOW": "#22c55e",
            }.get(alert.get("priority", "MEDIUM"), "#94a3b8")

            alert_rows += f"""
            <tr style="border-bottom: 1px solid #334155;">
                <td style="padding: 12px;">
                    <span style="font-weight: bold; color: white;">{alert.get('ticker', 'N/A')}</span>
                </td>
                <td style="padding: 12px;">
                    <span style="background-color: {priority_color}20; color: {priority_color}; padding: 4px 8px; border-radius: 4px; font-size: 12px;">
                        {alert.get('priority', 'MEDIUM')}
                    </span>
                </td>
                <td style="padding: 12px; color: #94a3b8;">{alert.get('message', '')}</td>
            </tr>
            """

        summary_section = ""
        if portfolio_summary:
            pnl_color = "#22c55e" if portfolio_summary.get("total_pnl", 0) >= 0 else "#ef4444"
            summary_section = f"""
            <div style="background-color: #334155; padding: 16px; border-radius: 8px; margin-bottom: 24px;">
                <h3 style="margin: 0 0 12px 0; color: #94a3b8; font-size: 14px;">Portfolio Summary</h3>
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;">
                    <div>
                        <p style="margin: 0; font-size: 12px; color: #64748b;">Total Value</p>
                        <p style="margin: 4px 0 0 0; font-size: 18px; font-weight: bold; color: white;">
                            ${portfolio_summary.get('total_value', 0):,.2f}
                        </p>
                    </div>
                    <div>
                        <p style="margin: 0; font-size: 12px; color: #64748b;">P&L</p>
                        <p style="margin: 4px 0 0 0; font-size: 18px; font-weight: bold; color: {pnl_color};">
                            ${portfolio_summary.get('total_pnl', 0):+,.2f}
                        </p>
                    </div>
                    <div>
                        <p style="margin: 0; font-size: 12px; color: #64748b;">Positions</p>
                        <p style="margin: 4px 0 0 0; font-size: 18px; font-weight: bold; color: white;">
                            {portfolio_summary.get('position_count', 0)}
                        </p>
                    </div>
                </div>
            </div>
            """

        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #0f172a; color: #e2e8f0; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #1e293b; border-radius: 12px; padding: 24px;">
                <h1 style="color: #ef4444; margin-bottom: 16px;">🚨 Portfolio Alerts</h1>
                <p style="color: #94a3b8; margin-bottom: 24px;">
                    You have {len(alerts)} alert(s) requiring your attention.
                </p>
                {summary_section}
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background-color: #334155;">
                            <th style="padding: 12px; text-align: left; color: #94a3b8; font-size: 12px;">TICKER</th>
                            <th style="padding: 12px; text-align: left; color: #94a3b8; font-size: 12px;">PRIORITY</th>
                            <th style="padding: 12px; text-align: left; color: #94a3b8; font-size: 12px;">MESSAGE</th>
                        </tr>
                    </thead>
                    <tbody>
                        {alert_rows}
                    </tbody>
                </table>
                <div style="margin-top: 24px; text-align: center;">
                    <a href="{self.base_url}/simulation"
                       style="background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold;">
                        View Dashboard
                    </a>
                </div>
                <p style="margin-top: 24px; font-size: 12px; color: #64748b; text-align: center;">
                    Silicon Oracle - AI-Powered Stock Monitoring
                </p>
            </div>
        </body>
        </html>
        """

    def _build_alert_email_text(
        self, alerts: List[Dict[str, Any]], portfolio_summary: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build plain text for alert notification email."""
        text = f"PORTFOLIO ALERTS - {len(alerts)} Action(s) Required\n\n"

        if portfolio_summary:
            text += f"""
Portfolio Summary:
- Total Value: ${portfolio_summary.get('total_value', 0):,.2f}
- P&L: ${portfolio_summary.get('total_pnl', 0):+,.2f}
- Positions: {portfolio_summary.get('position_count', 0)}

"""

        text += "ALERTS:\n"
        for alert in alerts:
            text += f"\n[{alert.get('priority', 'MEDIUM')}] {alert.get('ticker', 'N/A')}\n"
            text += f"  {alert.get('message', '')}\n"

        text += "\n\nView your dashboard for more details."
        return text

    def _build_digest_email_html(
        self,
        positions: List[Dict[str, Any]],
        news_items: List[Dict[str, Any]],
        portfolio_summary: Dict[str, Any],
    ) -> str:
        """Build HTML for daily digest email."""
        # Position rows
        position_rows = ""
        for pos in positions[:10]:
            pnl_color = "#22c55e" if pos.get("unrealized_pnl", 0) >= 0 else "#ef4444"
            position_rows += f"""
            <tr style="border-bottom: 1px solid #334155;">
                <td style="padding: 8px; font-weight: bold; color: white;">{pos.get('ticker', 'N/A')}</td>
                <td style="padding: 8px; color: #94a3b8;">${pos.get('live_price', 0):.2f}</td>
                <td style="padding: 8px; color: {pnl_color};">${pos.get('unrealized_pnl', 0):+.2f}</td>
                <td style="padding: 8px; color: {pnl_color};">{pos.get('unrealized_pnl_percent', 0):+.2f}%</td>
            </tr>
            """

        # News items
        news_section = ""
        if news_items:
            news_list = ""
            for item in news_items[:5]:
                news_list += f"""
                <li style="margin-bottom: 12px;">
                    <a href="{item.get('url', '#')}" style="color: #6366f1; text-decoration: none;">
                        {item.get('headline', 'News')[:80]}...
                    </a>
                    <p style="margin: 4px 0 0 0; font-size: 12px; color: #64748b;">
                        {item.get('ticker', '')} | {item.get('source', 'Unknown')}
                    </p>
                </li>
                """
            news_section = f"""
            <div style="margin-top: 24px;">
                <h3 style="color: #94a3b8; font-size: 14px; margin-bottom: 12px;">📰 Today's News</h3>
                <ul style="list-style: none; padding: 0; margin: 0;">
                    {news_list}
                </ul>
            </div>
            """

        pnl_color = "#22c55e" if portfolio_summary.get("total_pnl", 0) >= 0 else "#ef4444"

        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #0f172a; color: #e2e8f0; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #1e293b; border-radius: 12px; padding: 24px;">
                <h1 style="color: #6366f1; margin-bottom: 8px;">📊 Daily Portfolio Digest</h1>
                <p style="color: #64748b; margin-bottom: 24px;">{datetime.now().strftime('%B %d, %Y')}</p>

                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 24px;">
                    <div style="background-color: #334155; padding: 16px; border-radius: 8px;">
                        <p style="margin: 0; font-size: 12px; color: #64748b;">Total Value</p>
                        <p style="margin: 4px 0 0 0; font-size: 24px; font-weight: bold; color: white;">
                            ${portfolio_summary.get('total_value', 0):,.2f}
                        </p>
                    </div>
                    <div style="background-color: #334155; padding: 16px; border-radius: 8px;">
                        <p style="margin: 0; font-size: 12px; color: #64748b;">Today's P&L</p>
                        <p style="margin: 4px 0 0 0; font-size: 24px; font-weight: bold; color: {pnl_color};">
                            ${portfolio_summary.get('total_pnl', 0):+,.2f}
                        </p>
                    </div>
                </div>

                <h3 style="color: #94a3b8; font-size: 14px; margin-bottom: 12px;">📈 Holdings</h3>
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 16px;">
                    <thead>
                        <tr style="background-color: #334155;">
                            <th style="padding: 8px; text-align: left; color: #64748b; font-size: 11px;">TICKER</th>
                            <th style="padding: 8px; text-align: left; color: #64748b; font-size: 11px;">PRICE</th>
                            <th style="padding: 8px; text-align: left; color: #64748b; font-size: 11px;">P&L</th>
                            <th style="padding: 8px; text-align: left; color: #64748b; font-size: 11px;">%</th>
                        </tr>
                    </thead>
                    <tbody>
                        {position_rows}
                    </tbody>
                </table>

                {news_section}

                <div style="margin-top: 24px; text-align: center;">
                    <a href="{self.base_url}/simulation"
                       style="background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold;">
                        View Full Dashboard
                    </a>
                </div>
                <p style="margin-top: 24px; font-size: 12px; color: #64748b; text-align: center;">
                    Silicon Oracle - AI-Powered Stock Monitoring
                </p>
            </div>
        </body>
        </html>
        """

    def _build_digest_email_text(
        self,
        positions: List[Dict[str, Any]],
        news_items: List[Dict[str, Any]],
        portfolio_summary: Dict[str, Any],
    ) -> str:
        """Build plain text for daily digest email."""
        text = f"""
DAILY PORTFOLIO DIGEST - {datetime.now().strftime('%B %d, %Y')}

SUMMARY
-------
Total Value: ${portfolio_summary.get('total_value', 0):,.2f}
Today's P&L: ${portfolio_summary.get('total_pnl', 0):+,.2f}
Positions: {portfolio_summary.get('position_count', 0)}

HOLDINGS
--------
"""
        for pos in positions[:10]:
            text += f"{pos.get('ticker', 'N/A')}: ${pos.get('live_price', 0):.2f} ({pos.get('unrealized_pnl_percent', 0):+.2f}%)\n"

        if news_items:
            text += "\nTODAY'S NEWS\n------------\n"
            for item in news_items[:5]:
                text += f"- {item.get('headline', 'News')[:60]}...\n"

        text += "\nView your dashboard for more details."
        return text
