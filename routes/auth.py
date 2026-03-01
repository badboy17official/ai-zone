# ==============================================================================
# AI INTELLIGENCE ZONE — Control Arena
# Authentication Routes — Login, Register, JWT Token Management
# ==============================================================================

from datetime import datetime, timezone, timedelta

import jwt
from flask import Blueprint, request, jsonify, current_app, redirect, url_for, flash, render_template
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf.csrf import CSRFProtect

from models import db, User
from security import AuditLogger

auth_bp = Blueprint("auth", __name__)


# ==============================================================================
# WEB AUTH (Session-Based for Admin Panel)
# ==============================================================================

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Admin panel login page."""
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password) and user.is_active:
            # Check admin access
            if not user.is_admin:
                flash("Access denied. Admin privileges required.", "danger")
                AuditLogger.log("login_failed", f"Non-admin login attempt: {username}",
                              severity="warning")
                return render_template("auth/login.html"), 403

            login_user(user, remember=True)
            user.last_login = datetime.now(timezone.utc)
            user.last_login_ip = request.remote_addr
            user.login_count = (user.login_count or 0) + 1
            db.session.commit()

            AuditLogger.log("login_success", f"Admin login: {username}", user_id=user.id)
            flash(f"Welcome back, {user.username}!", "success")
            return redirect(url_for("admin.dashboard"))
        else:
            AuditLogger.log("login_failed", f"Failed login attempt for: {username}",
                          severity="warning")
            flash("Invalid credentials or account disabled.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    """Logout current user."""
    AuditLogger.log("logout", f"User logged out: {current_user.username}")
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


# ==============================================================================
# API AUTH (JWT-Based for Team Portal)
# ==============================================================================

@auth_bp.route("/api/token", methods=["POST"])
def get_token():
    """Issue JWT token for API access."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    username = data.get("username", "").strip()
    password = data.get("password", "")

    user = User.query.filter_by(username=username).first()

    if not user or not user.check_password(password) or not user.is_active:
        AuditLogger.log("token_request_failed", f"Failed token request for: {username}",
                      severity="warning")
        return jsonify({"error": "Invalid credentials"}), 401

    # Generate JWT
    expiry_hours = current_app.config.get("JWT_EXPIRY_HOURS", 8)
    payload = {
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=expiry_hours),
        "iat": datetime.now(timezone.utc),
    }

    token = jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256")

    # Update login tracking
    user.last_login = datetime.now(timezone.utc)
    user.last_login_ip = request.remote_addr
    user.login_count = (user.login_count or 0) + 1
    db.session.commit()

    AuditLogger.log("token_issued", f"JWT token issued for: {username}", user_id=user.id)

    return jsonify({
        "token": token,
        "expires_in": expiry_hours * 3600,
        "user": user.to_dict(),
    })


@auth_bp.route("/api/token/verify", methods=["POST"])
def verify_token():
    """Verify a JWT token is still valid."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"valid": False, "error": "Missing bearer token"}), 401

    token = auth_header.split(" ")[1]

    try:
        payload = jwt.decode(token, current_app.config["JWT_SECRET_KEY"], algorithms=["HS256"])
        user = User.query.get(payload["user_id"])
        if not user or not user.is_active:
            return jsonify({"valid": False, "error": "User not found or disabled"}), 401

        return jsonify({"valid": True, "user": user.to_dict()})
    except jwt.ExpiredSignatureError:
        return jsonify({"valid": False, "error": "Token expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"valid": False, "error": "Invalid token"}), 401


# ==============================================================================
# HELPER: JWT Required Decorator for API routes
# ==============================================================================
def jwt_required(f):
    """Decorator to require valid JWT for API endpoints."""
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authorization header with Bearer token required"}), 401

        token = auth_header.split(" ")[1]

        try:
            payload = jwt.decode(
                token, current_app.config["JWT_SECRET_KEY"], algorithms=["HS256"]
            )
            user = User.query.get(payload["user_id"])
            if not user or not user.is_active:
                return jsonify({"error": "User account not found or disabled"}), 401

            # Attach user to request context
            from flask import g
            g.current_user = user
            g.current_user_id = user.id

        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        return f(*args, **kwargs)
    return decorated
