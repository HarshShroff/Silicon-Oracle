"""
BYOK Encryption Utilities for Silicon Oracle.
Encrypts/decrypts user API keys before storing in database.
"""
import base64
import hashlib
import os
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def get_encryption_key() -> bytes:
    """
    Get or generate the master encryption key.
    In production, this should come from environment/secrets.
    """
    # Try to get from environment first
    key = os.environ.get("ENCRYPTION_KEY")
    if key:
        # If it's a string, encode it
        if isinstance(key, str):
            # Ensure it's valid Fernet key (32 url-safe base64 bytes)
            if len(key) == 44:  # Fernet key length
                return key.encode()
            # Otherwise derive a key from it
            return derive_key_from_password(key)
        return key

    # Try Streamlit secrets if available (for Streamlit app)
    try:
        import streamlit as st
        key = st.secrets.get("encryption", {}).get("key")
        if key:
            if isinstance(key, str):
                if len(key) == 44:
                    return key.encode()
                return derive_key_from_password(key)
            return key
    except (ImportError, Exception):
        pass

    # Fallback: Generate a key from a default salt (for local dev only)
    # WARNING: In production, always use a proper secret!
    default_secret = os.environ.get(
        "SECRET_KEY", "silicon-oracle-local-dev-key-change-in-production")
    return derive_key_from_password(default_secret)


def derive_key_from_password(password: str, salt: Optional[bytes] = None) -> bytes:
    """
    Derive a Fernet-compatible key from a password using PBKDF2.
    """
    if salt is None:
        # Use a consistent salt for the app (in production, store this securely)
        salt = b"silicon-oracle-salt-v1"

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,  # OWASP recommended minimum
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key


def encrypt_value(plaintext: str) -> str:
    """
    Encrypt a string value (e.g., API key) for storage.
    Returns base64-encoded ciphertext.
    """
    if not plaintext:
        return ""

    try:
        key = get_encryption_key()
        f = Fernet(key)
        encrypted = f.encrypt(plaintext.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    except Exception as e:
        # Log error but don't expose details
        import logging
        logging.error(f"Encryption error: {e}")
        return ""


def decrypt_value(ciphertext: str) -> str:
    """
    Decrypt a stored value back to plaintext.
    Returns empty string if decryption fails.
    """
    if not ciphertext:
        return ""

    try:
        key = get_encryption_key()
        f = Fernet(key)
        # Decode from our storage format
        encrypted = base64.urlsafe_b64decode(ciphertext.encode())
        decrypted = f.decrypt(encrypted)
        return decrypted.decode()
    except Exception as e:
        # Don't expose decryption errors in production
        return ""


def hash_password(password: str) -> str:
    """
    Hash a password for storage (one-way).
    Note: Supabase Auth handles this automatically,
    but useful for local testing.
    """
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode(),
        salt,
        100000
    )
    return base64.b64encode(salt + key).decode()


def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verify a password against its hash.
    """
    try:
        decoded = base64.b64decode(stored_hash.encode())
        salt = decoded[:32]
        stored_key = decoded[32:]
        new_key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode(),
            salt,
            100000
        )
        return new_key == stored_key
    except Exception:
        return False


# --- API Key Helpers ---

def encrypt_api_keys(keys: dict) -> dict:
    """
    Encrypt a dictionary of API keys for storage.
    Input: {"alpaca_api_key": "xxx", "alpaca_secret": "yyy", ...}
    Output: {"alpaca_api_key_encrypted": "...", ...}
    """
    encrypted = {}
    for key, value in keys.items():
        if value and not key.endswith("_encrypted"):
            encrypted[f"{key}_encrypted"] = encrypt_value(value)
    return encrypted


def decrypt_api_keys(encrypted_keys: dict) -> dict:
    """
    Decrypt a dictionary of encrypted API keys.
    Input: {"alpaca_api_key_encrypted": "...", ...}
    Output: {"alpaca_api_key": "xxx", ...}
    """
    decrypted = {}
    for key, value in encrypted_keys.items():
        if key.endswith("_encrypted") and value:
            clean_key = key.replace("_encrypted", "")
            decrypted[clean_key] = decrypt_value(value)
    return decrypted
