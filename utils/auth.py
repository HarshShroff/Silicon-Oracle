"""
Authentication Module for Silicon Oracle.
Handles user signup, login, session management via Supabase Auth.
Falls back to local mode (no auth) for development.
"""
import streamlit as st
from typing import Optional, Dict, Any
from datetime import datetime

# Logging
from utils.logging_config import get_logger

logger = get_logger(__name__)


# ============================================
# SUPABASE AUTH CLIENT
# ============================================

def get_auth_client():
    """Get Supabase auth client."""
    try:
        from utils.database import get_supabase_client
        client = get_supabase_client()
        if client:
            return client.auth
    except Exception:
        pass
    return None


def is_auth_enabled() -> bool:
    """Check if authentication is configured."""
    return get_auth_client() is not None


# ============================================
# SESSION MANAGEMENT
# ============================================

def get_current_user() -> Optional[Dict[str, Any]]:
    """
    Get currently logged-in user from session state.
    Returns user dict with id, email, etc. or None if not logged in.
    """
    return st.session_state.get("user")


def get_current_user_id() -> Optional[str]:
    """Get current user's ID (UUID string)."""
    user = get_current_user()
    return user.get("id") if user else None


def is_logged_in() -> bool:
    """Check if user is currently logged in."""
    return get_current_user() is not None


def set_user_session(user_data: Dict[str, Any]):
    """Store user data in session state after successful login."""
    st.session_state["user"] = user_data
    st.session_state["login_time"] = datetime.now().isoformat()


def clear_user_session():
    """Clear user session (logout)."""
    if "user" in st.session_state:
        del st.session_state["user"]
    if "login_time" in st.session_state:
        del st.session_state["login_time"]
    # Clear any cached user-specific data
    if "user_api_keys" in st.session_state:
        del st.session_state["user_api_keys"]


# ============================================
# AUTHENTICATION FUNCTIONS
# ============================================

def get_app_url() -> str:
    """
    Get the app URL for redirects.
    Uses Streamlit secrets in production, falls back to localhost for dev.
    """
    try:
        # Check for configured app URL in secrets
        app_url = st.secrets.get("app", {}).get("url")
        if app_url:
            return app_url.rstrip('/')
    except Exception:
        pass
    return "http://localhost:8501"


def sign_up(email: str, password: str) -> Dict[str, Any]:
    """
    Register a new user with email and password.
    Returns {"success": True, "user": {...}} or {"success": False, "error": "..."}
    """
    auth = get_auth_client()

    if not auth:
        return {"success": False, "error": "Authentication not configured. Running in local mode."}

    try:
        redirect_url = get_app_url()
        response = auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "email_redirect_to": redirect_url
            }
        })

        if response.user:
            # We rely on Supabase SQL Trigger or Login Self-Healing to create the profile.
            # Calling create_user_profile here often fails RLS before email confirmation.
            # Pass silently.
            pass

            return {
                "success": True,
                "user": {
                    "id": str(response.user.id),
                    "email": response.user.email,
                    "created_at": str(response.user.created_at)
                },
                "message": "Account created! Please check your email to verify."
            }
        else:
            return {"success": False, "error": "Signup failed. Please try again."}

    except Exception as e:
        error_msg = str(e)
        if "already registered" in error_msg.lower():
            return {"success": False, "error": "This email is already registered. Please login."}
        return {"success": False, "error": f"Signup error: {error_msg}"}


def sign_in(email: str, password: str) -> Dict[str, Any]:
    """
    Log in an existing user.
    Returns {"success": True, "user": {...}} or {"success": False, "error": "..."}
    """
    logger.info(f"Sign-in attempt for: {email}")
    auth = get_auth_client()

    if not auth:
        # Local development mode - auto-login with fake user
        logger.info("No auth client - using local dev mode")
        fake_user = {
            "id": "local-dev-user",
            "email": email,
            "created_at": datetime.now().isoformat()
        }
        set_user_session(fake_user)
        return {
            "success": True,
            "user": fake_user,
            "message": "Logged in (local dev mode)"
        }

    try:
        # logger.debug("Attempting Supabase sign-in...")
        response = auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if response.user:
            user_data = {
                "id": str(response.user.id),
                "email": response.user.email,
                "created_at": str(response.user.created_at)
            }
            set_user_session(user_data)
            logger.info(
                f"Sign-in successful for user: {user_data['id'][:8]}...")

            # Self-healing: Ensure profile exists (fix for users who failed RLS during signup)
            from utils.database import get_user_profile, create_user_profile
            try:
                if not get_user_profile(user_data["id"]):
                    logger.info("Creating missing user profile...")
                    create_user_profile(user_data["id"], user_data["email"])
            except Exception as e:
                logger.warning(f"Profile creation failed: {e}")

            # Update last login in profile
            from utils.database import update_user_profile
            update_user_profile(
                user_data["id"], {"last_login": datetime.now().isoformat()})

            return {"success": True, "user": user_data}
        else:
            return {"success": False, "error": "Login failed. Please check your credentials."}

    except Exception as e:
        error_msg = str(e)
        if "invalid" in error_msg.lower():
            return {"success": False, "error": "Invalid email or password."}
        return {"success": False, "error": f"Login error: {error_msg}"}


def sign_out() -> bool:
    """Log out the current user."""
    auth = get_auth_client()

    try:
        if auth:
            auth.sign_out()
    except Exception:
        pass

    clear_user_session()
    return True


def reset_password(email: str) -> Dict[str, Any]:
    """
    Send password reset email.
    Returns {"success": True} or {"success": False, "error": "..."}
    """
    auth = get_auth_client()

    if not auth:
        return {"success": False, "error": "Authentication not configured."}

    try:
        redirect_url = get_app_url()
        auth.reset_password_email(email, {
            "redirect_to": redirect_url
        })
        return {"success": True, "message": "Password reset email sent. Check your inbox."}
    except Exception as e:
        return {"success": False, "error": f"Reset error: {e}"}


# ============================================
# USER API KEYS (BYOK)
# ============================================

def get_user_decrypted_keys() -> Dict[str, str]:
    """
    Get decrypted API keys for current user.
    Caches in session state to avoid repeated decryption.
    """
    user_id = get_current_user_id()
    if not user_id:
        return {}

    # Check cache first
    cache_key = f"user_api_keys_{user_id}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]

    # Fetch and decrypt
    from utils.database import get_user_api_keys
    from utils.encryption import decrypt_api_keys

    encrypted = get_user_api_keys(user_id)
    if not encrypted:
        return {}

    decrypted = decrypt_api_keys(encrypted)

    # Cache for this session
    st.session_state[cache_key] = decrypted
    return decrypted


def save_user_api_keys(keys: Dict[str, str]) -> bool:
    """
    Encrypt and save API keys for current user.
    Input: {"alpaca_api_key": "xxx", "alpaca_secret_key": "yyy", ...}
    """
    user_id = get_current_user_id()
    if not user_id:
        return False

    from utils.encryption import encrypt_api_keys
    from utils.database import save_user_api_keys as db_save_keys

    encrypted = encrypt_api_keys(keys)
    success = db_save_keys(user_id, encrypted)

    if success:
        # Clear cache to force re-fetch
        cache_key = f"user_api_keys_{user_id}"
        if cache_key in st.session_state:
            del st.session_state[cache_key]

    return success


def clear_api_keys_cache():
    """Clear cached API keys (call when user updates keys)."""
    user_id = get_current_user_id()
    if user_id:
        cache_key = f"user_api_keys_{user_id}"
        if cache_key in st.session_state:
            del st.session_state[cache_key]


# ============================================
# AUTH UI COMPONENTS
# ============================================

def render_login_form():
    """Render login/signup form in Streamlit."""
    st.title("Silicon Oracle")
    st.caption("AI-Powered Trading Assistant")

    tab1, tab2 = st.tabs(["Login", "Sign Up"])

    with tab1:
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input(
                "Password", type="password", key="login_password")
            submitted = st.form_submit_button("Login", width='stretch')

            if submitted:
                if not email or not password:
                    st.error("Please enter email and password.")
                else:
                    result = sign_in(email, password)
                    if result["success"]:
                        st.success("Logged in successfully!")
                        st.rerun()
                    else:
                        st.error(result["error"])

        if st.button("Forgot Password?", key="forgot_btn"):
            st.session_state["show_reset"] = True

        if st.session_state.get("show_reset"):
            reset_email = st.text_input("Enter your email", key="reset_email")
            if st.button("Send Reset Link"):
                result = reset_password(reset_email)
                if result["success"]:
                    st.success(result["message"])
                else:
                    st.error(result["error"])

    with tab2:
        with st.form("signup_form"):
            new_email = st.text_input("Email", key="signup_email")
            new_password = st.text_input(
                "Password", type="password", key="signup_password")
            confirm_password = st.text_input(
                "Confirm Password", type="password", key="confirm_password")
            submitted = st.form_submit_button(
                "Create Account", width='stretch')

            if submitted:
                if not new_email or not new_password:
                    st.error("Please fill in all fields.")
                elif new_password != confirm_password:
                    st.error("Passwords do not match.")
                elif len(new_password) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    result = sign_up(new_email, new_password)
                    if result["success"]:
                        st.success(result.get("message", "Account created!"))
                        st.info("You can now log in with your credentials.")
                    else:
                        st.error(result["error"])


def render_user_menu():
    """Render user menu in sidebar (when logged in)."""
    user = get_current_user()
    if not user:
        return

    with st.sidebar:
        st.divider()
        st.write(f"**{user['email']}**")
        if st.button("Logout", key="logout_btn", width='stretch'):
            sign_out()
            st.rerun()


def require_auth():
    """
    Decorator/check to require authentication.
    Returns True if user is logged in, False otherwise.
    Use at the start of pages that require login.
    """
    if not is_logged_in():
        render_login_form()
        st.stop()
    return True


# ============================================
# LOCAL DEV MODE
# ============================================

def enable_local_dev_mode():
    """
    Enable local development mode (no auth required).
    Creates a fake user session for testing.
    """
    if not is_logged_in():
        fake_user = {
            "id": "local-dev-user",
            "email": "dev@localhost",
            "created_at": datetime.now().isoformat()
        }
        set_user_session(fake_user)
        return True
    return False


def is_local_dev_mode() -> bool:
    """Check if running in local dev mode."""
    user = get_current_user()
    return user and user.get("id") == "local-dev-user"
