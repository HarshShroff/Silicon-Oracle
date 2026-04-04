"""
Silicon Oracle - Auth Routes
Database-backed authentication with signup and API key management.
BYOK (Bring Your Own Keys) - Users must provide their own API keys.
"""

import re
from datetime import datetime
from typing import Optional, Tuple

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from utils import database as db

auth_bp = Blueprint("auth", __name__)

# Disposable email domains to block
_DISPOSABLE_DOMAINS = {
    "mailinator.com",
    "guerrillamail.com",
    "guerrillamail.net",
    "guerrillamail.org",
    "guerrillamail.biz",
    "guerrillamail.de",
    "guerrillamail.info",
    "sharklasers.com",
    "guerrillamailblock.com",
    "grr.la",
    "guerrillamail.com",
    "spam4.me",
    "trashmail.com",
    "trashmail.me",
    "trashmail.net",
    "trashmail.at",
    "trashmail.io",
    "trashmail.org",
    "dispostable.com",
    "yopmail.com",
    "yopmail.fr",
    "cool.fr.nf",
    "jetable.fr.nf",
    "nospam.ze.tc",
    "nomail.xl.cx",
    "mega.zik.dj",
    "speed.1s.fr",
    "courriel.fr.nf",
    "moncourrier.fr.nf",
    "monemail.fr.nf",
    "monmail.fr.nf",
    "tempmail.com",
    "temp-mail.org",
    "throwam.com",
    "throwam.net",
    "fakeinbox.com",
    "maildrop.cc",
    "mailnull.com",
    "spamgourmet.com",
    "10minutemail.com",
    "10minutemail.net",
    "10minutemail.org",
    "minutemail.com",
    "discard.email",
    "cuvox.de",
    "dayrep.com",
    "einrot.com",
    "fleckens.hu",
    "gustr.com",
    "jourrapide.com",
    "rhyta.com",
    "superrito.com",
    "teleworm.us",
}


def _validate_email(email: str) -> Tuple[bool, str]:
    """
    Validate email address:
    1. Basic format check
    2. Disposable domain block
    3. MX record lookup (domain has real mail servers)
    Returns (is_valid, error_message).
    """
    email = email.strip().lower()

    # 1. Format
    pattern = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
    if not pattern.match(email):
        return False, "Please enter a valid email address."

    domain = email.split("@")[1]

    # 2. Disposable domains
    if domain in _DISPOSABLE_DOMAINS:
        return False, "Disposable email addresses are not allowed."

    # 3. MX record check
    try:
        import dns.resolver

        dns.resolver.resolve(domain, "MX")
    except Exception:
        return False, f"The domain '{domain}' doesn't appear to accept email."

    return True, ""


def setup_user_session(user_id: str, email: Optional[str] = None):
    """Set up a persistent user session across all tabs."""
    session["user_id"] = user_id
    if email:
        session["user_email"] = email
    session["logged_in_at"] = datetime.now().isoformat()
    session.permanent = True  # Use PERMANENT_SESSION_LIFETIME from config


@auth_bp.route("/validate-email", methods=["POST"])
def validate_email():
    """AJAX endpoint — check email format, disposable domain, and MX record."""
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    if not email:
        return jsonify({"valid": False, "error": "Email is required."})
    valid, error = _validate_email(email)
    return jsonify({"valid": valid, "error": error})


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Login page."""
    # If already logged in, redirect to dashboard
    if session.get("user_id"):
        return redirect(url_for("main.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        if not email or not password:
            flash("Please enter both email and password", "error")
            return render_template("pages/login.html")

        try:
            client = db.get_supabase_client()
            if not client:
                flash("Database connection failed. Please try again.", "error")
                return render_template("pages/login.html")

            # Authenticate with Supabase
            try:
                res = client.auth.sign_in_with_password({"email": email, "password": password})
                user = res.user

                if user:
                    # Block unconfirmed accounts
                    if user.confirmed_at is None:
                        flash(
                            "Please confirm your email address before logging in. Check your inbox for the confirmation link.",
                            "error",
                        )
                        return render_template("pages/login.html")

                    # Set up persistent session (email stored for fallback)
                    setup_user_session(user.id, email=email)

                    # Ensure profile exists (Supabase trigger may have created it)
                    profile = db.get_user_profile(user.id)
                    if not profile:
                        db.create_user_profile(user.id, email)

                    # Check if user has API keys configured
                    api_keys = db.get_user_api_keys(user.id, decrypt=True)
                    if not api_keys.get("FINNHUB_API_KEY"):
                        flash(
                            "Welcome back! Please configure your API keys to use all features.",
                            "info",
                        )
                        return redirect(url_for("main.settings"))

                    flash("Welcome back!", "success")
                    return redirect(url_for("main.index"))

            except Exception as auth_err:
                current_app.logger.error(f"Login error: {auth_err}")
                flash("Invalid email or password", "error")

        except Exception as e:
            current_app.logger.error(f"Login exception: {e}")
            flash("An error occurred. Please try again.", "error")

    return render_template("pages/login.html")


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    """Sign up page for new users. BYOK - Users must provide their own API keys."""
    # If already logged in, redirect to dashboard
    if session.get("user_id"):
        return redirect(url_for("main.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        errors = []
        if not username or len(username) < 3:
            errors.append("Username must be at least 3 characters")

        if not email:
            errors.append("Please enter a valid email address")
        else:
            valid, email_error = _validate_email(email)
            if not valid:
                errors.append(email_error)

        if not password or len(password) < 12:
            errors.append("Password must be at least 12 characters")

        if password != confirm_password:
            errors.append("Passwords do not match")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("pages/signup.html", email=email, username=username)

        try:
            client = db.get_supabase_client()
            if not client:
                flash("Database configuration error. Please try again later.", "error")
                return render_template("pages/signup.html", email=email, username=username)

            # Check for existing email before hitting Supabase auth
            # (Supabase silently returns the existing user on duplicate when confirmation is on)
            existing = db.get_user_by_email(email)
            if existing:
                flash("An account with this email already exists. Please log in instead.", "error")
                return render_template("pages/signup.html", email=email, username=username)

            # Signup with Supabase Auth
            res = client.auth.sign_up({"email": email, "password": password})
            user = res.user

            if user:
                # Create profile now (before confirmation) so username is saved
                profile = db.get_user_profile(user.id)
                if profile:
                    db.update_user_profile(user.id, {"username": username})
                else:
                    db.create_user_profile(user_id=user.id, email=email, username=username)

                # Check if Supabase requires email confirmation
                # user.confirmed_at is None when email confirmation is enabled
                if user.confirmed_at is None:
                    flash(
                        "Account created! Check your email and click the confirmation link to activate your account.",
                        "success",
                    )
                    return redirect(url_for("auth.login"))
                else:
                    # Email confirmation disabled — log in immediately
                    setup_user_session(user.id, email=email)
                    flash(
                        "Account created! Please configure your API keys (BYOK - Bring Your Own Keys).",
                        "success",
                    )
                    return redirect(url_for("main.settings"))
            else:
                flash("Signup failed. Email may already be registered.", "error")

        except Exception as e:
            current_app.logger.error(f"Signup exception: {e}")
            error_msg = str(e).lower()
            if "already registered" in error_msg or "duplicate" in error_msg:
                flash("This email is already registered. Please log in instead.", "error")
            else:
                flash("Error creating account. Please try again.", "error")
            return render_template("pages/signup.html", email=email, username=username)

    return render_template("pages/signup.html", email="", username="")


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    """Logout user."""
    session.clear()
    response = redirect(url_for("auth.login"))
    flash("You have been logged out.", "info")
    return response
