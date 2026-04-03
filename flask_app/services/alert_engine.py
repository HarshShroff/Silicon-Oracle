import logging
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class AlertEngine:
    """
    Evaluates positions against Sentinel alert logic.
    """

    def __init__(self):
        pass

    def check_position(
        self, position: Dict[str, Any], data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Check a single position for alerts based on latest market data.

        Args:
            position: The ShadowPosition dictionary
            data: Dictionary containing 'price', 'score', 'earnings'

        Returns:
            List of alert dictionaries.
        """
        alerts: List[Dict[str, Any]] = []
        current_price = data.get("price", 0.0)
        current_score = data.get("score", 0.0)
        earnings_data = data.get("earnings")

        if current_price <= 0:
            return alerts

        # 1. Trailing Stop Alert (8% drop from highest seen)
        highest = max(position.get("highest_price_seen", 0.0), current_price)
        drop_pct = (highest - current_price) / highest if highest > 0 else 0

        if drop_pct >= 0.08:
            alerts.append(
                {
                    "type": "TRAILING_STOP",
                    "priority": "HIGH",
                    "message": f"Price dropped {drop_pct * 100:.1f}% from peak of ${highest:.2f}",
                    "details": {
                        "current": current_price,
                        "highest": highest,
                        "drop_pct": drop_pct,
                    },
                }
            )

        # 2. Oracle Reversal
        # Check if we have a previous score to compare against
        if position.get("last_oracle_score") is not None:
            prev_score = position["last_oracle_score"]
            # Alert if dropping from healthy (>7) to weak (<4)
            if prev_score >= 7.0 and current_score < 4.0:
                alerts.append(
                    {
                        "type": "ORACLE_REVERSAL",
                        "priority": "CRITICAL",
                        "message": f"Oracle Score collapsed from {prev_score} to {current_score}",
                        "details": {
                            "prev_score": prev_score,
                            "current_score": current_score,
                        },
                    }
                )

        # 3. Earnings Warning (within 3 days)
        if earnings_data and earnings_data.get("date"):
            try:
                earn_date = datetime.strptime(earnings_data["date"], "%Y-%m-%d")
                days_until = (earn_date - datetime.now()).days

                if 0 <= days_until <= 3:
                    alerts.append(
                        {
                            "type": "EARNINGS_SOON",
                            "priority": "MEDIUM",
                            "message": f"Earnings coming up in {days_until} days ({earnings_data['date']})",
                            "details": {
                                "date": earnings_data["date"],
                                "days": days_until,
                            },
                        }
                    )
            except Exception as e:
                logger.error(f"Date parse error in alert engine: {e}")

        # 4. Volatility/Surge (Price spike > 15% from avg entry)
        gain_pct = (current_price - position["average_entry_price"]) / position[
            "average_entry_price"
        ]
        if gain_pct >= 0.15:
            # Only alert if this is "rapid" or "new"?
            # Sentinel doesn't track history of alerts well yet, so this might spam.
            # We'll leave it as a "High Performance" alert for now.
            pass

        return alerts
