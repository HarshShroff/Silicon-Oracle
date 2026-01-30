from datetime import datetime
from flask import Blueprint, jsonify, request, g
from utils import database as db

sentinel_bp = Blueprint("sentinel", __name__)


# Removed get_user_id_from_request to prevent parameter spoofing.
# Always use g.user.id for security.


@sentinel_bp.route("/add", methods=["POST"])
def add_position():
    """Add a new position to Sentinel monitoring."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    required_fields = ["ticker", "quantity", "average_entry_price"]
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    # Get user_id from session ONLY
    if not hasattr(g, 'user') or not g.user:
        return jsonify({"error": "User not authenticated"}), 401
    user_id = g.user.id

    try:
        from utils.ticker_utils import normalize_ticker

        # Handle date parsing if provided
        earnings_date = None
        if data.get("next_earnings_date"):
            earnings_date = datetime.fromisoformat(
                str(data["next_earnings_date"]).replace("Z", "")
            ).date()

        # Normalize ticker (handles BRK.B, etc.)
        ticker = normalize_ticker(data["ticker"])

        position_data = {
            "ticker": ticker,
            "quantity": float(data["quantity"]),
            "average_entry_price": float(data["average_entry_price"]),
            "highest_price_seen": float(data["average_entry_price"]),
            "last_oracle_score": data.get("oracle_score"),
            "next_earnings_date": earnings_date,
        }

        success = db.add_shadow_position(user_id, position_data)

        if success:
            return jsonify(
                {
                    "message": "Position added to Sentinel",
                }
            ), 201
        else:
            return jsonify({"error": "Failed to add position"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@sentinel_bp.route("/dashboard", methods=["GET"])
def dashboard():
    """Get all active monitored positions."""
    try:
        if not hasattr(g, 'user') or not g.user:
            return jsonify({"error": "User not authenticated", "positions": [], "count": 0}), 401
        user_id = g.user.id

        positions = db.get_shadow_positions(user_id, is_active=True)
        return jsonify({"positions": positions, "count": len(positions)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sentinel_bp.route("/sync", methods=["POST"])
def sync_sentinel():
    """Manually trigger a Sentinel sync/check."""
    from flask import current_app
    from flask_app.services.sentinel_engine import SentinelEngine

    try:
        if not hasattr(g, 'user') or not g.user:
            return jsonify({"error": "User not authenticated"}), 401
        user_id = g.user.id

        # Run synchronously for now to see immediate results in UI/Logs
        engine = SentinelEngine(current_app)
        engine.run_cycle(user_id)

        return jsonify({"message": "Sentinel sync completed", "status": "success"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
