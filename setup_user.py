"""
One-time setup script to create user and migrate existing API keys.
Run this once to set up your account in Supabase.
"""
import streamlit as st
from supabase import create_client

# Load secrets
import tomllib
with open(".streamlit/secrets.toml", "rb") as f:
    secrets = tomllib.load(f)

# Supabase client
supabase = create_client(
    secrets["supabase"]["url"],
    secrets["supabase"]["anon_key"]
)

# User credentials
EMAIL = "harshrofff+SO@gmail.com"
PASSWORD = "HungryTrumpet967!"

print("=" * 50)
print("Silicon Oracle - User Setup")
print("=" * 50)

# Step 1: Sign up the user
print("\n1. Creating user account...")
try:
    response = supabase.auth.sign_up({
        "email": EMAIL,
        "password": PASSWORD
    })

    if response.user:
        user_id = response.user.id
        print(f"   ✓ User created: {EMAIL}")
        print(f"   ✓ User ID: {user_id}")
    else:
        print("   ✗ Signup failed - user may already exist")
        # Try to sign in instead
        print("\n   Attempting to sign in...")
        response = supabase.auth.sign_in_with_password({
            "email": EMAIL,
            "password": PASSWORD
        })
        if response.user:
            user_id = response.user.id
            print(f"   ✓ Signed in: {EMAIL}")
            print(f"   ✓ User ID: {user_id}")
        else:
            print("   ✗ Could not sign in")
            exit(1)

except Exception as e:
    error_msg = str(e)
    if "already registered" in error_msg.lower():
        print(f"   User already exists. Signing in...")
        try:
            response = supabase.auth.sign_in_with_password({
                "email": EMAIL,
                "password": PASSWORD
            })
            user_id = response.user.id
            print(f"   ✓ Signed in: {EMAIL}")
            print(f"   ✓ User ID: {user_id}")
        except Exception as e2:
            print(f"   ✗ Sign in failed: {e2}")
            exit(1)
    else:
        print(f"   ✗ Error: {e}")
        exit(1)

# Step 2: Encrypt API keys
print("\n2. Encrypting API keys...")
from utils.encryption import encrypt_value

keys_to_encrypt = {
    "alpaca_api_key": secrets.get("alpaca", {}).get("api_key", ""),
    "alpaca_secret_key": secrets.get("alpaca", {}).get("secret_key", ""),
    "finnhub_api_key": secrets.get("finnhub", {}).get("api_key", ""),
    "gemini_api_key": secrets.get("gemini", {}).get("api_key", ""),
}

encrypted_keys = {}
for key_name, value in keys_to_encrypt.items():
    if value:
        encrypted_keys[f"{key_name}_encrypted"] = encrypt_value(value)
        print(f"   ✓ Encrypted: {key_name}")

# Step 3: Create/update user profile
print("\n3. Creating user profile...")
try:
    profile_data = {
        "id": user_id,
        "email": EMAIL,
        "starting_capital": secrets.get("trading", {}).get("starting_capital", 500),
        "risk_profile": "moderate",
        "notifications_enabled": False,
        **encrypted_keys
    }

    # Use upsert to handle existing profiles
    supabase.table("user_profiles").upsert(profile_data).execute()
    print(f"   ✓ Profile created/updated")
    print(f"   ✓ API keys linked to account")

except Exception as e:
    print(f"   ✗ Error creating profile: {e}")
    print("\n   Trying alternative approach (insert)...")
    try:
        supabase.table("user_profiles").insert(profile_data).execute()
        print(f"   ✓ Profile inserted")
    except Exception as e2:
        print(f"   ✗ Insert also failed: {e2}")
        print("\n   You may need to run the SQL schema first in Supabase SQL Editor.")

# Step 4: Verify
print("\n4. Verifying setup...")
try:
    result = supabase.table("user_profiles").select("email, starting_capital, risk_profile").eq("id", user_id).single().execute()
    if result.data:
        print(f"   ✓ Profile verified:")
        print(f"     - Email: {result.data.get('email')}")
        print(f"     - Capital: ${result.data.get('starting_capital')}")
        print(f"     - Risk: {result.data.get('risk_profile')}")
except Exception as e:
    print(f"   ⚠ Could not verify (RLS may be blocking): {e}")

print("\n" + "=" * 50)
print("Setup complete!")
print("=" * 50)
print(f"\nYou can now log in with:")
print(f"  Email: {EMAIL}")
print(f"  Password: {'*' * len(PASSWORD)}")
print("\nRun: streamlit run app.py")
