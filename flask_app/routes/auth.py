"""
Silicon Oracle - Auth Routes
Database-backed authentication with signup and API key management.
BYOK (Bring Your Own Keys) - Users must provide their own API keys.
"""

from datetime import datetime
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify,
    current_app,
)
from utils import database as db

auth_bp = Blueprint("auth", __name__)


def setup_user_session(user_id: str, email: str = None):
    """Set up a persistent user session across all tabs."""
    session["user_id"] = user_id
    if email:
        session["user_email"] = email
    session["logged_in_at"] = datetime.now().isoformat()
    session.permanent = True  # Use PERMANENT_SESSION_LIFETIME from config


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
                res = client.auth.sign_in_with_password(
                    {"email": email, "password": password})
                user = res.user

                if user:
                    # Set up persistent session (email stored for fallback)
                    setup_user_session(user.id, email=email)

                    # Ensure profile exists (Supabase trigger may have created it)
                    profile = db.get_user_profile(user.id)
                    if not profile:
                        db.create_user_profile(user.id, email)

                    # Check if user has API keys configured
                    api_keys = db.get_user_api_keys(user.id, decrypt=True)
                    if not api_keys.get("FINNHUB_API_KEY"):
                        flash("Welcome back! Please configure your API keys to use all features.", "info")
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

        if not email or "@" not in email:
            errors.append("Please enter a valid email address")

        if not password or len(password) < 6:
            errors.append("Password must be at least 6 characters")

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

            # Signup with Supabase Auth
            res = client.auth.sign_up({"email": email, "password": password})
            user = res.user

            if user:
                # Set up persistent session immediately
                setup_user_session(user.id, email=email)

                # Try to create/update profile with username
                # Note: Supabase trigger may have already created the profile
                profile = db.get_user_profile(user.id)
                if profile:
                    # Profile exists (from trigger), update with username
                    db.update_user_profile(user.id, {"username": username})
                else:
                    # Create new profile
                    db.create_user_profile(user_id=user.id, email=email, username=username)

                flash(
                    "Account created! Please configure your API keys (BYOK - Bring Your Own Keys).",
                    "success",
                )
                # Always redirect to settings for BYOK setup
                return redirect(url_for("main.settings"))
            else:
                flash("Signup failed. Email may already be registered.", "error")

        except Exception as e:
            current_app.logger.error(f"Signup exception: {e}")
            # Check for common errors
            error_msg = str(e).lower()
            if "already registered" in error_msg or "duplicate" in error_msg:
                flash("This email is already registered. Please log in instead.", "error")
            else:
                flash(f"Error creating account. Please try again.", "error")
            return render_template("pages/signup.html", email=email, username=username)

    return render_template("pages/signup.html", email="", username="")


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    """Logout user."""
    session.clear()
    response = redirect(url_for("auth.login"))
    flash("You have been logged out.", "info")
    return response
