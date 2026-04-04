"""
Tests for flask_app/services/alert_engine.py
"""

from datetime import datetime, timedelta

import pytest

from flask_app.services.alert_engine import AlertEngine


@pytest.fixture
def engine():
    return AlertEngine()


@pytest.fixture
def base_position():
    return {
        "ticker": "AAPL",
        "shares": 10,
        "average_entry_price": 150.0,
        "highest_price_seen": 160.0,
        "last_oracle_score": None,
    }


@pytest.fixture
def base_data():
    return {
        "price": 155.0,
        "score": 8.0,
        "earnings": None,
    }


class TestZeroPriceGuard:
    def test_zero_price_returns_no_alerts(self, engine, base_position):
        alerts = engine.check_position(base_position, {"price": 0, "score": 5})
        assert alerts == []

    def test_negative_price_returns_no_alerts(self, engine, base_position):
        alerts = engine.check_position(base_position, {"price": -1, "score": 5})
        assert alerts == []

    def test_missing_price_returns_no_alerts(self, engine, base_position):
        alerts = engine.check_position(base_position, {"score": 5})
        assert alerts == []


class TestTrailingStop:
    def test_no_alert_below_threshold(self, engine, base_position, base_data):
        """5% drop should not trigger (threshold is 8%)."""
        base_position["highest_price_seen"] = 160.0
        base_data["price"] = 152.0  # 5% drop from 160
        alerts = engine.check_position(base_position, base_data)
        types = [a["type"] for a in alerts]
        assert "TRAILING_STOP" not in types

    def test_alert_at_threshold(self, engine, base_position, base_data):
        """Exactly 8% drop triggers alert."""
        base_position["highest_price_seen"] = 100.0
        base_data["price"] = 92.0  # exactly 8% drop
        alerts = engine.check_position(base_position, base_data)
        types = [a["type"] for a in alerts]
        assert "TRAILING_STOP" in types

    def test_alert_above_threshold(self, engine, base_position, base_data):
        """10% drop triggers alert."""
        base_position["highest_price_seen"] = 200.0
        base_data["price"] = 180.0  # 10% drop
        alerts = engine.check_position(base_position, base_data)
        types = [a["type"] for a in alerts]
        assert "TRAILING_STOP" in types

    def test_trailing_stop_uses_current_if_higher(self, engine, base_position, base_data):
        """If current price > highest_seen, highest updates — no alert."""
        base_position["highest_price_seen"] = 100.0
        base_data["price"] = 120.0  # new high, no drop
        alerts = engine.check_position(base_position, base_data)
        types = [a["type"] for a in alerts]
        assert "TRAILING_STOP" not in types

    def test_trailing_stop_priority_is_high(self, engine, base_position, base_data):
        base_position["highest_price_seen"] = 200.0
        base_data["price"] = 180.0
        alerts = engine.check_position(base_position, base_data)
        stop_alerts = [a for a in alerts if a["type"] == "TRAILING_STOP"]
        assert stop_alerts[0]["priority"] == "HIGH"

    def test_trailing_stop_details(self, engine, base_position, base_data):
        base_position["highest_price_seen"] = 200.0
        base_data["price"] = 180.0
        alerts = engine.check_position(base_position, base_data)
        stop = next(a for a in alerts if a["type"] == "TRAILING_STOP")
        assert stop["details"]["current"] == 180.0
        assert stop["details"]["highest"] == 200.0
        assert abs(stop["details"]["drop_pct"] - 0.10) < 0.001


class TestOracleReversal:
    def test_no_alert_without_previous_score(self, engine, base_position, base_data):
        base_position["last_oracle_score"] = None
        base_data["score"] = 2.0
        alerts = engine.check_position(base_position, base_data)
        types = [a["type"] for a in alerts]
        assert "ORACLE_REVERSAL" not in types

    def test_alert_when_score_collapses(self, engine, base_position, base_data):
        """Score dropping from 8 → 3 triggers ORACLE_REVERSAL."""
        base_position["last_oracle_score"] = 8.0
        base_data["score"] = 3.0
        alerts = engine.check_position(base_position, base_data)
        types = [a["type"] for a in alerts]
        assert "ORACLE_REVERSAL" in types

    def test_no_alert_when_score_stays_healthy(self, engine, base_position, base_data):
        base_position["last_oracle_score"] = 8.0
        base_data["score"] = 7.5
        alerts = engine.check_position(base_position, base_data)
        types = [a["type"] for a in alerts]
        assert "ORACLE_REVERSAL" not in types

    def test_no_alert_when_prev_score_below_threshold(self, engine, base_position, base_data):
        """Prev score 6.0 (< 7.0) dropping to 2.0 doesn't trigger."""
        base_position["last_oracle_score"] = 6.0
        base_data["score"] = 2.0
        alerts = engine.check_position(base_position, base_data)
        types = [a["type"] for a in alerts]
        assert "ORACLE_REVERSAL" not in types

    def test_oracle_reversal_priority_is_critical(self, engine, base_position, base_data):
        base_position["last_oracle_score"] = 9.0
        base_data["score"] = 1.0
        alerts = engine.check_position(base_position, base_data)
        rev = next(a for a in alerts if a["type"] == "ORACLE_REVERSAL")
        assert rev["priority"] == "CRITICAL"

    def test_exact_boundary_prev_7_current_3_99(self, engine, base_position, base_data):
        """Exactly at boundary: prev=7.0, current=3.99 → alert fires."""
        base_position["last_oracle_score"] = 7.0
        base_data["score"] = 3.99
        alerts = engine.check_position(base_position, base_data)
        types = [a["type"] for a in alerts]
        assert "ORACLE_REVERSAL" in types

    def test_boundary_current_exactly_4_no_alert(self, engine, base_position, base_data):
        """current_score = 4.0 is NOT < 4.0, so no alert."""
        base_position["last_oracle_score"] = 8.0
        base_data["score"] = 4.0
        alerts = engine.check_position(base_position, base_data)
        types = [a["type"] for a in alerts]
        assert "ORACLE_REVERSAL" not in types


class TestEarningsWarning:
    def test_no_alert_without_earnings_data(self, engine, base_position, base_data):
        base_data["earnings"] = None
        alerts = engine.check_position(base_position, base_data)
        types = [a["type"] for a in alerts]
        assert "EARNINGS_SOON" not in types

    def test_alert_when_earnings_in_2_days(self, engine, base_position, base_data):
        future_date = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        base_data["earnings"] = {"date": future_date}
        alerts = engine.check_position(base_position, base_data)
        types = [a["type"] for a in alerts]
        assert "EARNINGS_SOON" in types

    def test_alert_when_earnings_tomorrow(self, engine, base_position, base_data):
        future_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        base_data["earnings"] = {"date": future_date}
        alerts = engine.check_position(base_position, base_data)
        types = [a["type"] for a in alerts]
        assert "EARNINGS_SOON" in types

    def test_no_alert_when_earnings_far_away(self, engine, base_position, base_data):
        future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        base_data["earnings"] = {"date": future_date}
        alerts = engine.check_position(base_position, base_data)
        types = [a["type"] for a in alerts]
        assert "EARNINGS_SOON" not in types

    def test_no_alert_for_past_earnings(self, engine, base_position, base_data):
        past_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        base_data["earnings"] = {"date": past_date}
        alerts = engine.check_position(base_position, base_data)
        types = [a["type"] for a in alerts]
        assert "EARNINGS_SOON" not in types

    def test_invalid_date_does_not_raise(self, engine, base_position, base_data):
        base_data["earnings"] = {"date": "not-a-date"}
        alerts = engine.check_position(base_position, base_data)  # should not raise
        assert isinstance(alerts, list)

    def test_earnings_priority_is_medium(self, engine, base_position, base_data):
        future_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        base_data["earnings"] = {"date": future_date}
        alerts = engine.check_position(base_position, base_data)
        earn = next(a for a in alerts if a["type"] == "EARNINGS_SOON")
        assert earn["priority"] == "MEDIUM"


class TestMultipleAlerts:
    def test_multiple_alerts_can_fire_simultaneously(self, engine):
        """A position can generate both TRAILING_STOP and ORACLE_REVERSAL."""
        position = {
            "ticker": "TEST",
            "average_entry_price": 100.0,
            "highest_price_seen": 200.0,
            "last_oracle_score": 9.0,
        }
        future_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        data = {
            "price": 180.0,  # 10% drop from 200 → TRAILING_STOP
            "score": 2.0,  # collapsed from 9 → ORACLE_REVERSAL
            "earnings": {"date": future_date},  # → EARNINGS_SOON
        }
        alerts = engine.check_position(position, data)
        types = {a["type"] for a in alerts}
        assert "TRAILING_STOP" in types
        assert "ORACLE_REVERSAL" in types
        assert "EARNINGS_SOON" in types
