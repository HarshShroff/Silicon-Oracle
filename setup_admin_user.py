#!/usr/bin/env python3
"""
Silicon Oracle — Admin User Setup Script

Creates (or resets) a local admin/demo user in Supabase with all API keys
pre-loaded from environment variables (.env file).

Usage:
    python3.11 setup_admin_user.py

Credentials created:
    Email:    admin@siliconoracle.dev
    Password: SiliconAdmin2025!

All API keys are read from .env — nothing is hardcoded here.
"""

import os
import sys

# ── Load .env first ──────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✓ Loaded .env")
except ImportError:
    print("⚠  python-dotenv not installed. Run: pip install python-dotenv")
    sys.exit(1)

# ── Read API keys from env (set in .env, never hardcoded) ────────────────────
ALPACA_API_KEY    = os.environ.get("ADMIN_ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.environ.get("ADMIN_ALPACA_SECRET_KEY", "")
GEMINI_API_KEY    = os.environ.get("ADMIN_GEMINI_API_KEY", "")
FINNHUB_API_KEY   = os.environ.get("ADMIN_FINNHUB_API_KEY", "")
GMAIL_ADDRESS     = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_PASSWORD    = os.environ.get("GMAIL_APP_PASSWORD", "")

ADMIN_EMAIL    = "admin@siliconoracle.dev"
ADMIN_PASSWORD = "SiliconAdmin2025!"
ADMIN_USERNAME = "admin"

missing = [k for k, v in {
    "ADMIN_ALPACA_API_KEY": ALPACA_API_KEY,
    "ADMIN_ALPACA_SECRET_KEY": ALPACA_SECRET_KEY,
    "ADMIN_GEMINI_API_KEY": GEMINI_API_KEY,
    "ADMIN_FINNHUB_API_KEY": FINNHUB_API_KEY,
}.items() if not v]

if missing:
    print(f"✗  Missing env vars: {', '.join(missing)}")
    print("   Add them to your .env file and re-run.")
    sys.exit(1)

print(f"\nSetting up admin user: {ADMIN_EMAIL}")

# ── Supabase client ───────────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("✗  SUPABASE_URL / SUPABASE_ANON_KEY not set in .env")
    sys.exit(1)

try:
    from supabase import create_client
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✓ Supabase connected")
except Exception as e:
    print(f"✗  Supabase connection failed: {e}")
    sys.exit(1)

# ── Create or retrieve Supabase Auth user ─────────────────────────────────────
# Service role key allows creating users without email confirmation.
# If only anon key is available, we fall back to sign_up (requires email confirm).
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
admin_client = None
if SERVICE_KEY:
    try:
        admin_client = create_client(SUPABASE_URL, SERVICE_KEY)
        print("✓ Using service role key (no email confirmation needed)")
    except Exception as e:
        print(f"⚠  Service client failed: {e}")

user_id = None

# Path 1: Admin API (service key) — no email confirmation
if admin_client:
    try:
        res = admin_client.auth.admin.create_user({
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
            "email_confirm": True,
        })
        if res.user:
            user_id = res.user.id
            print(f"✓ Created user via admin API: {user_id}")
    except Exception as e:
        err = str(e)
        if "already been registered" in err or "already registered" in err or "duplicate" in err.lower():
            print("⚠  User already exists — looking up existing user...")
            try:
                # List users to find existing one
                users_resp = admin_client.auth.admin.list_users()
                for u in users_resp:
                    if hasattr(u, 'email') and u.email == ADMIN_EMAIL:
                        user_id = u.id
                        print(f"✓ Found existing user: {user_id}")
                        break
            except Exception as e2:
                print(f"⚠  Could not list users: {e2}")
        else:
            print(f"⚠  Admin create failed: {e}")

# Path 2: Regular sign-in (user already confirmed in Supabase)
if not user_id:
    try:
        res = client.auth.sign_in_with_password({"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        if res.user:
            user_id = res.user.id
            print(f"✓ Signed in as existing user: {user_id}")
    except Exception as e:
        print(f"⚠  Sign-in failed: {e}")

# Path 3: Regular sign-up (sends confirmation email)
if not user_id:
    try:
        res = client.auth.sign_up({"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        if res.user:
            user_id = res.user.id
            print(f"✓ Sign-up submitted: {user_id}")
            print("⚠  NOTE: Supabase sent a confirmation email to", ADMIN_EMAIL)
            print("   After confirming, re-run this script to finish saving API keys.")
    except Exception as e:
        print(f"✗  All auth paths failed: {e}")

if not user_id:
    print("\n✗  Could not create or find user.")
    print("\nFix options:")
    print("  A) Add SUPABASE_SERVICE_KEY to .env (get from Supabase dashboard → Settings → API)")
    print("  B) Supabase dashboard → Auth → Settings → disable 'Enable email confirmations'")
    print("     Then re-run this script.")
    sys.exit(1)

# ── Ensure user_profiles row exists ──────────────────────────────────────────
from datetime import datetime
profile_data = {
    "id": user_id,
    "email": ADMIN_EMAIL,
    "username": ADMIN_USERNAME,
    "created_at": datetime.utcnow().isoformat(),
    "starting_capital": 100000,
    "risk_profile": "moderate",
    "notifications_enabled": True,
}
try:
    # Upsert so re-running the script is safe
    client.table("user_profiles").upsert(profile_data).execute()
    print("✓ user_profiles row upserted")
except Exception as e:
    print(f"⚠  Profile upsert warning: {e}")

# ── Encrypt and save API keys ─────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from utils.encryption import encrypt_value
except Exception as e:
    print(f"✗  Could not import encryption util: {e}")
    sys.exit(1)

encrypted = {
    "alpaca_api_key_encrypted":    encrypt_value(ALPACA_API_KEY),
    "alpaca_secret_key_encrypted": encrypt_value(ALPACA_SECRET_KEY),
    "gemini_api_key_encrypted":    encrypt_value(GEMINI_API_KEY),
    "finnhub_api_key_encrypted":   encrypt_value(FINNHUB_API_KEY),
    "gmail_address":               GMAIL_ADDRESS,
}
if GMAIL_PASSWORD:
    encrypted["gmail_app_password_encrypted"] = encrypt_value(GMAIL_PASSWORD)

try:
    client.table("user_profiles").update(encrypted).eq("id", user_id).execute()
    print("✓ API keys encrypted and saved")
except Exception as e:
    print(f"✗  Failed to save API keys: {e}")
    sys.exit(1)

# ── Save default simulation settings ─────────────────────────────────────────
sim_settings = {
    "user_id": user_id,
    "trading_style": "swing_trading",
    "price_alerts": True,
    "news_alerts": True,
    "daily_digest": True,
    "email_alerts": True,
}
try:
    client.table("simulation_settings").upsert(sim_settings).execute()
    print("✓ Simulation settings saved")
except Exception as e:
    print(f"⚠  Simulation settings warning (table may not exist): {e}")

# ── Done ──────────────────────────────────────────────────────────────────────
print("\n" + "="*52)
print("  Admin user ready.")
print(f"  URL:      http://localhost:5001")
print(f"  Email:    {ADMIN_EMAIL}")
print(f"  Password: {ADMIN_PASSWORD}")
print("="*52 + "\n")
