"""
Database Layer for Silicon Oracle.
Supports both Supabase (production) and SQLite (local development).
Compatible with both Flask and Streamlit environments.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
import json
import os
import logging

logger = logging.getLogger(__name__)

# Cache for Supabase client (singleton pattern)
_supabase_client = None
_supabase_initialized = False


# ============================================
# SUPABASE CLIENT
# ============================================


def get_supabase_client():
    """
    Get Supabase client if credentials are configured.
    Returns None if Supabase is not configured (falls back to SQLite).
    Uses singleton pattern for caching.
    """
    global _supabase_client, _supabase_initialized

    if _supabase_initialized:
        return _supabase_client

    _supabase_initialized = True

    try:
        from supabase import create_client, Client

        url = None
        key = None

        # Try Streamlit secrets first (if available)
        try:
            import streamlit as st
            url = st.secrets.get("supabase", {}).get("url")
            key = st.secrets.get("supabase", {}).get("service_role_key")
            if not key:
                key = st.secrets.get("supabase", {}).get("anon_key")
        except Exception:
            pass

        # Fallback to Environment Variables
        if not url:
            url = os.environ.get("SUPABASE_URL")

        if not key:
            key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get(
                "SUPABASE_ANON_KEY")

        if url and key:
            _supabase_client = create_client(url, key)
            return _supabase_client

    except ImportError:
        logger.warning("Supabase not installed. Using SQLite fallback.")
    except Exception as e:
        logger.warning(f"Failed to initialize Supabase: {e}")

    return None


def is_supabase_enabled() -> bool:
    """Check if Supabase is configured and available."""
    return get_supabase_client() is not None


# ============================================
# USER PROFILES (BYOK Keys Storage)
# ============================================


def get_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user profile with encrypted API keys."""
    client = get_supabase_client()
    if not client:
        logger.warning(f"Supabase client not available when fetching profile for {user_id}")
        return None

    try:
        response = (
            client.table("user_profiles")
            .select("*")
            .eq("id", user_id)
            .single()
            .execute()
        )
        return response.data
    except Exception as e:
        logger.error(f"Failed to get user profile for {user_id}: {type(e).__name__}: {str(e)}")
        return None


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Get user profile by email."""
    client = get_supabase_client()
    if not client:
        return None

    try:
        response = (
            client.table("user_profiles")
            .select("*")
            .eq("email", email)
            .single()
            .execute()
        )
        return response.data
    except Exception:
        return None


def create_user_profile(user_id: str, email: str, username: str = None) -> bool:
    """Create a new user profile after signup."""
    client = get_supabase_client()
    if not client:
        return False

    try:
        profile_data = {
            "id": user_id,
            "email": email,
            "created_at": datetime.now().isoformat(),
            "starting_capital": 500,
            "risk_profile": "moderate",
            "notifications_enabled": False,
        }
        # Add username if provided
        if username:
            profile_data["username"] = username

        client.table("user_profiles").insert(profile_data).execute()
        return True
    except Exception:
        # Fail silently (e.g. RLS violation); let caller handle or rely on Trigger
        return False


def update_user_profile(user_id: str, data: Dict[str, Any]) -> bool:
    """Update user profile (API keys, settings, etc.)."""
    client = get_supabase_client()
    if not client:
        return False

    try:
        client.table("user_profiles").update(data).eq("id", user_id).execute()
        return True
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        return False


def save_user_api_keys(user_id: str, api_keys: Dict[str, str]) -> bool:
    """Save API keys to user profile with encryption."""
    try:
        from utils.encryption import encrypt_value

        encrypted_keys = {}
        for key, value in api_keys.items():
            if value and not key.endswith("_encrypted"):
                # Encrypt the value
                encrypted_keys[f"{key}_encrypted"] = encrypt_value(value)
            elif key.endswith("_encrypted"):
                # Already encrypted, pass through
                encrypted_keys[key] = value

        return update_user_profile(user_id, encrypted_keys)
    except Exception as e:
        logger.error(f"Error saving API keys: {e}")
        return False


def get_user_api_keys(user_id: str, decrypt: bool = True) -> Dict[str, str]:
    """Get API keys from user profile with optional decryption."""
    profile = get_user_profile(user_id)
    if not profile:
        return {}

    # Extract only the encrypted key fields
    key_fields = [
        "alpaca_api_key_encrypted",
        "alpaca_secret_key_encrypted",
        "finnhub_api_key_encrypted",
        "gemini_api_key_encrypted",
        "gmail_address",
        "gmail_app_password_encrypted",
    ]

    keys = {k: profile.get(k, "") for k in key_fields if profile.get(k)}

    if decrypt:
        try:
            from utils.encryption import decrypt_value
            decrypted_keys = {}

            # Map database field names to service key names
            key_mapping = {
                "alpaca_api_key_encrypted": "ALPACA_API_KEY",
                "alpaca_secret_key_encrypted": "ALPACA_SECRET_KEY",
                "finnhub_api_key_encrypted": "FINNHUB_API_KEY",
                "gemini_api_key_encrypted": "GEMINI_API_KEY",
                "gmail_app_password_encrypted": "GMAIL_APP_PASSWORD",
            }

            for key, value in keys.items():
                if key.endswith("_encrypted") and value:
                    # Decrypt and return with uppercase key name for services
                    service_key = key_mapping.get(
                        key, key.replace("_encrypted", "").upper())
                    decrypted_keys[service_key] = decrypt_value(value)
                elif key == "gmail_address":
                    decrypted_keys["GMAIL_ADDRESS"] = value

            return decrypted_keys
        except Exception as e:
            logger.error(f"Error decrypting API keys: {e}")
            return {}

    return keys


# ============================================
# POSITIONS (User's Stock Holdings)
# ============================================


def get_user_positions(user_id: str) -> List[Dict[str, Any]]:
    """Get all positions for a user."""
    client = get_supabase_client()
    if not client:
        return []

    try:
        response = (
            client.table("positions").select(
                "*").eq("user_id", user_id).execute()
        )
        return response.data or []
    except Exception:
        return []


def get_user_trades(user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Get trade history for a user."""
    client = get_supabase_client()
    if not client:
        return []

    try:
        response = (
            client.table("trades")
            .select("*")
            .eq("user_id", user_id)
            .order("timestamp", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []
    except Exception:
        return []


def upsert_position(user_id: str, ticker: str, shares: float, avg_price: float) -> bool:
    """Insert or update a position."""
    client = get_supabase_client()
    if not client:
        return False

    try:
        now = datetime.now().isoformat()
        client.table("positions").upsert(
            {
                "user_id": user_id,
                "ticker": ticker,
                "shares": shares,
                "avg_price": avg_price,
                "entry_date": now,
                "last_updated": now,
            },
            on_conflict="user_id,ticker",
        ).execute()
        return True
    except Exception as e:
        logger.error(f"Error saving position: {e}")
        return False


def delete_position(user_id: str, ticker: str) -> bool:
    """Delete a position (when fully sold)."""
    client = get_supabase_client()
    if not client:
        return False

    try:
        client.table("positions").delete().eq("user_id", user_id).eq(
            "ticker", ticker
        ).execute()
        return True
    except Exception:
        return False


# ============================================
# ACCOUNT HISTORY (Balance Snapshots)
# ============================================
def record_account_snapshot(
    user_id: str,
    cash: float,
    buying_power: float,
    portfolio_value: float,
    equity: float,
) -> bool:
    """Record an account balance snapshot."""
    client = get_supabase_client()
    if not client:
        return False

    try:
        client.table("account_history").insert(
            {
                "user_id": user_id,
                "timestamp": datetime.now().isoformat(),
                "cash": cash,
                "buying_power": buying_power,
                "portfolio_value": portfolio_value,
                "equity": equity,
            }
        ).execute()
        return True
    except Exception:
        return False


def get_account_history(user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Get account balance history."""
    client = get_supabase_client()
    if not client:
        return []

    try:
        response = (
            client.table("account_history")
            .select("*")
            .eq("user_id", user_id)
            .order("timestamp", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []
    except Exception:
        return []


def get_sentinel_history(user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Get performance history for the simulation/sentinel portfolio."""
    client = get_supabase_client()
    if not client:
        return []

    try:
        response = (
            client.table("simulation_history")
            .select("*")
            .eq("user_id", user_id)
            .order("timestamp", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []
    except Exception:
        # Table might not exist yet; returning empty list allows backfill logic to kick in
        return []


def record_sentinel_snapshot(user_id: str, data: Dict[str, Any]) -> bool:
    """Record a snapshot of the shadow portfolio value."""
    client = get_supabase_client()
    if not client:
        return False

    try:
        data["user_id"] = user_id
        data["timestamp"] = datetime.now().isoformat()
        client.table("simulation_history").insert(data).execute()
        return True
    except Exception:
        # Silently fail if table doesn't exist
        return False


# ============================================
# SHADOW PORTFOLIO (SENTINEL)
# ============================================


def get_shadow_positions(user_id: str, is_active: bool = True) -> List[Dict[str, Any]]:
    """Get all shadow positions for a user."""
    client = get_supabase_client()
    if not client:
        return []

    try:
        response = (
            client.table("shadow_positions")
            .select("*")
            .eq("user_id", user_id)
            .eq("is_active", is_active)
            .execute()
        )
        return response.data or []
    except Exception as e:
        logger.error(f"Error getting shadow positions: {e}")
        return []


def add_shadow_position(user_id: str, data: Dict[str, Any]) -> bool:
    """Add a new shadow position."""
    client = get_supabase_client()
    if not client:
        logger.error("Supabase client not available")
        return False

    try:
        data["user_id"] = user_id
        # Ensure dates are compatible if passed as objects
        if "date_purchased" not in data:
            data["date_purchased"] = datetime.now().isoformat()
        if "created_at" not in data:
            data["created_at"] = datetime.now().isoformat()
        if "updated_at" not in data:
            data["updated_at"] = datetime.now().isoformat()

        logger.info(
            f"Adding shadow position for user {user_id}: {data.get('ticker')}")
        result = client.table("shadow_positions").insert(data).execute()
        logger.info(f"Position added successfully: {result.data}")
        return True
    except Exception as e:
        logger.error(f"Error adding shadow position: {e}")
        return False


def update_shadow_position(
    position_id: int, user_id: str, data: Dict[str, Any]
) -> bool:
    """Update a shadow position."""
    client = get_supabase_client()
    if not client:
        return False

    try:
        data["updated_at"] = datetime.now().isoformat()
        client.table("shadow_positions").update(data).eq("id", position_id).eq(
            "user_id", user_id
        ).execute()
        return True
    except Exception as e:
        logger.error(f"Error updating shadow position: {e}")
        return False


def delete_shadow_position(position_id: int, user_id: str) -> bool:
    """Delete a shadow position."""
    client = get_supabase_client()
    if not client:
        return False

    try:
        client.table("shadow_positions").delete().eq("id", position_id).eq(
            "user_id", user_id
        ).execute()
        return True
    except Exception as e:
        logger.error(f"Error deleting shadow position: {e}")
        return False


def record_trade(user_id: str, trade_data: Dict[str, Any]) -> bool:
    """Record a new trade."""
    client = get_supabase_client()
    if not client:
        return False

    try:
        trade_data["user_id"] = user_id
        trade_data["timestamp"] = trade_data.get(
            "timestamp", datetime.now().isoformat()
        )
        client.table("trades").insert(trade_data).execute()
        return True
    except Exception as e:
        # Ignore duplicate errors (already synced)
        if "duplicate" not in str(e).lower():
            logger.error(f"Error recording trade: {e}")
        return False


# ============================================
# SIMULATION SETTINGS
# ============================================


def get_simulation_settings(user_id: str) -> Optional[Dict[str, Any]]:
    """Get simulation settings for a user."""
    client = get_supabase_client()
    if not client:
        return None

    try:
        response = (
            client.table("simulation_settings")
            .select("*")
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        return response.data
    except Exception:
        return None


def update_simulation_settings(user_id: str, settings: Dict[str, Any]) -> bool:
    """Update or create simulation settings for a user."""
    client = get_supabase_client()
    if not client:
        return False

    try:
        settings["user_id"] = user_id
        settings["updated_at"] = datetime.now().isoformat()

        client.table("simulation_settings").upsert(
            settings, on_conflict="user_id"
        ).execute()
        return True
    except Exception as e:
        logger.error(f"Error updating simulation settings: {e}")
        return False


def get_notification_preferences(user_id: str) -> Dict[str, Any]:
    """Get notification preferences for a user."""
    settings = get_simulation_settings(user_id)
    if not settings:
        # Default preferences
        return {
            "email_alerts": True,
            "price_alerts": True,
            "news_alerts": True,
            "daily_digest": True,
            "alert_threshold_percent": 5.0,
            "digest_time": "08:00"
        }

    return {
        "email_alerts": settings.get("email_alerts", True),
        "price_alerts": settings.get("price_alerts", True),
        "news_alerts": settings.get("news_alerts", True),
        "daily_digest": settings.get("daily_digest", True),
        "alert_threshold_percent": settings.get("alert_threshold_percent", 5.0),
        "digest_time": settings.get("digest_time", "08:00")
    }


# ============================================
# WATCHLISTS
# ============================================


def get_user_watchlists(user_id: str) -> List[Dict[str, Any]]:
    """Get all watchlists for a user."""
    client = get_supabase_client()
    if not client:
        return []

    try:
        response = (
            client.table("watchlists").select(
                "*").eq("user_id", user_id).execute()
        )
        return response.data or []
    except Exception:
        return []


def create_watchlist(user_id: str, name: str, tickers: List[str]) -> Optional[int]:
    """Create a new watchlist."""
    client = get_supabase_client()
    if not client:
        return None

    try:
        response = (
            client.table("watchlists")
            .insert(
                {
                    "user_id": user_id,
                    "name": name,
                    "tickers": tickers,
                    "created_at": datetime.now().isoformat(),
                }
            )
            .execute()
        )
        return response.data[0]["id"] if response.data else None
    except Exception as e:
        logger.error(f"Error creating watchlist: {e}")
        return None


def update_watchlist(watchlist_id: int, user_id: str, data: Dict[str, Any]) -> bool:
    """Update a watchlist (name, tickers, etc.)."""
    client = get_supabase_client()
    if not client:
        return False

    try:
        client.table("watchlists").update(data).eq("id", watchlist_id).eq(
            "user_id", user_id
        ).execute()
        return True
    except Exception:
        return False


def delete_watchlist(watchlist_id: int, user_id: str) -> bool:
    """Delete a watchlist."""
    client = get_supabase_client()
    if not client:
        return False

    try:
        client.table("watchlists").delete().eq("id", watchlist_id).eq(
            "user_id", user_id
        ).execute()
        return True
    except Exception:
        return False


# ============================================
# AI SCAN RESULTS (Cached Recommendations)
# ============================================


def save_scan_results(user_id: str, results: List[Dict[str, Any]]) -> bool:
    """Save AI scan results for a user."""
    client = get_supabase_client()
    if not client:
        return False

    try:
        now = datetime.now().isoformat()
        for result in results:
            result["user_id"] = user_id
            result["scanned_at"] = now
            # Convert factors dict to JSON string for storage
            if "factors" in result and isinstance(result["factors"], dict):
                result["factors"] = json.dumps(result["factors"])

        client.table("ai_scan_results").upsert(
            results, on_conflict="user_id,ticker"
        ).execute()
        return True
    except Exception as e:
        logger.error(f"Error saving scan results: {e}")
        return False


def get_scan_results(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Get cached AI scan results for a user."""
    client = get_supabase_client()
    if not client:
        return []

    try:
        response = (
            client.table("ai_scan_results")
            .select("*")
            .eq("user_id", user_id)
            .order("oracle_score", desc=True)
            .limit(limit)
            .execute()
        )
        results = response.data or []

        # Parse factors JSON back to dict
        for r in results:
            if r.get("factors") and isinstance(r["factors"], str):
                try:
                    r["factors"] = json.loads(r["factors"])
                except Exception:
                    r["factors"] = {}

        return results
    except Exception:
        return []


# ============================================
# DATABASE INITIALIZATION (Run Once)
# ============================================


def get_schema_sql() -> str:
    """
    Return SQL to create all tables.
    Run this in Supabase SQL Editor to initialize the database.
    """
    return """
-- users table (legacy/external auth)
CREATE TABLE IF NOT EXISTS public.users (
  id integer NOT NULL DEFAULT nextval('users_id_seq'::regclass),
  username character varying NOT NULL,
  email character varying NOT NULL,
  password_hash character varying NOT NULL,
  finnhub_api_key character varying,
  alpaca_api_key character varying,
  alpaca_secret_key character varying,
  gemini_api_key character varying,
  email_notifications boolean,
  sms_notifications boolean,
  phone_number character varying,
  created_at timestamp without time zone,
  updated_at timestamp without time zone,
  last_login timestamp without time zone,
  CONSTRAINT users_pkey PRIMARY KEY (id)
);

-- user_profiles (linked to auth.users, similar to previous schema but matching request)
CREATE TABLE IF NOT EXISTS public.user_profiles (
  id uuid NOT NULL,
  email text NOT NULL UNIQUE,
  created_at timestamp without time zone DEFAULT now(),
  last_login timestamp without time zone,
  alpaca_api_key_encrypted text,
  alpaca_secret_key_encrypted text,
  finnhub_api_key_encrypted text,
  gemini_api_key_encrypted text,
  gmail_address text,
  gmail_app_password_encrypted text,
  notifications_enabled boolean DEFAULT false,
  starting_capital real DEFAULT 500,
  risk_profile text DEFAULT 'moderate'::text,
  CONSTRAINT user_profiles_pkey PRIMARY KEY (id),
  CONSTRAINT user_profiles_id_fkey FOREIGN KEY (id) REFERENCES auth.users(id)
);

-- positions/trades tables usually link to user_profiles (UUID)
CREATE TABLE IF NOT EXISTS public.trades (
  id integer NOT NULL DEFAULT nextval('trades_id_seq'::regclass),
  user_id uuid,
  ticker text NOT NULL,
  action text NOT NULL,
  shares real NOT NULL,
  price real NOT NULL,
  total_value real NOT NULL,
  reason text,
  timestamp timestamp without time zone NOT NULL,
  alpaca_order_id text,
  CONSTRAINT trades_pkey PRIMARY KEY (id),
  CONSTRAINT trades_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.user_profiles(id)
);

CREATE TABLE IF NOT EXISTS public.account_history (
  id integer NOT NULL DEFAULT nextval('account_history_id_seq'::regclass),
  user_id uuid,
  timestamp timestamp without time zone NOT NULL,
  cash real,
  buying_power real,
  portfolio_value real,
  equity real,
  CONSTRAINT account_history_pkey PRIMARY KEY (id),
  CONSTRAINT account_history_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.user_profiles(id)
);

-- Standard Positions (if needed, mimicking trades/holdings)
-- Note: The provided schema didn't explicitly show a 'positions' table separate from shadow_positions,
-- but the app seems to use it. If not provided in request, we keep existing or infer.
-- Assuming standard usage might rely on 'trades' or 'positions' table not detailed in snippet,
-- but we stick to what IS provided. The snippet had 'shadow_positions'.

CREATE TABLE IF NOT EXISTS public.shadow_positions (
  id integer NOT NULL DEFAULT nextval('shadow_positions_id_seq'::regclass),
  user_id integer NOT NULL, -- Integer ID referencing users(id)
  ticker character varying NOT NULL,
  quantity double precision NOT NULL,
  average_entry_price double precision NOT NULL,
  date_purchased timestamp without time zone,
  highest_price_seen double precision,
  next_earnings_date timestamp without time zone,
  last_oracle_score double precision,
  is_active boolean,
  created_at timestamp without time zone,
  updated_at timestamp without time zone,
  CONSTRAINT shadow_positions_pkey PRIMARY KEY (id),
  CONSTRAINT shadow_positions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id)
);

CREATE TABLE IF NOT EXISTS public.ai_scan_results (
  id integer NOT NULL DEFAULT nextval('ai_scan_results_id_seq'::regclass),
  user_id uuid,
  ticker text NOT NULL,
  oracle_score real,
  verdict text,
  confidence real,
  reasoning text,
  factors jsonb,
  scanned_at timestamp without time zone DEFAULT now(),
  CONSTRAINT ai_scan_results_pkey PRIMARY KEY (id),
  CONSTRAINT ai_scan_results_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.user_profiles(id)
);

CREATE TABLE IF NOT EXISTS public.watchlists (
  id integer NOT NULL DEFAULT nextval('watchlists_id_seq'::regclass),
  user_id uuid,
  name text NOT NULL,
  tickers ARRAY NOT NULL,
  alpaca_watchlist_id text,
  created_at timestamp without time zone DEFAULT now(),
  CONSTRAINT watchlists_pkey PRIMARY KEY (id),
  CONSTRAINT watchlists_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.user_profiles(id)
);

-- Initial Function/Trigger as before
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.user_profiles (id, email)
  VALUES (new.id, new.email);
  RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger the function every time a user is created
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();
"""
