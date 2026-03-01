# ==============================================================================
# AI INTELLIGENCE ZONE — Control Arena
# Main Flask Application — App Factory + Blueprint Registration
# ==============================================================================

import os
import logging
from datetime import datetime, timezone

from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_cors import CORS

from config import get_config
from models import db, User


login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_class=None):
    """Application factory — creates and configures the Flask app."""

    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    # ── Load Configuration ────────────────────────────────────────────
    if config_class:
        app.config.from_object(config_class)
    else:
        app.config.from_object(get_config())

    # ── Initialize Extensions ─────────────────────────────────────────
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": app.config.get("CORS_ORIGINS", "*")}})

    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(user_id)

    # ── Register Blueprints ───────────────────────────────────────────
    from routes.admin import admin_bp
    from routes.api import api_bp
    from routes.auth import auth_bp

    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/auth")

    # Exempt API routes from CSRF (they use JWT)
    csrf.exempt(api_bp)
    csrf.exempt(auth_bp)  # Auth blueprint: login form still renders csrf_token, API routes use JWT

    # ── Create Database Tables ────────────────────────────────────────
    with app.app_context():
        db.create_all()
        _seed_admin_if_needed(app)

    # ── Logging ───────────────────────────────────────────────────────
    _configure_logging(app)

    # ── Context Processors ────────────────────────────────────────────
    @app.context_processor
    def inject_globals():
        return {
            "competition_name": app.config.get("COMPETITION_NAME", "Control Arena"),
            "current_year": datetime.now().year,
            "now": datetime.now(timezone.utc),
        }

    # ── Error Handlers ────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return {"error": "Resource not found", "status": 404}, 404

    @app.errorhandler(403)
    def forbidden(e):
        return {"error": "Access forbidden", "status": 403}, 403

    @app.errorhandler(429)
    def rate_limited(e):
        return {"error": "Rate limit exceeded. Please slow down.", "status": 429}, 429

    @app.errorhandler(500)
    def server_error(e):
        return {"error": "Internal server error", "status": 500}, 500

    return app


def _seed_admin_if_needed(app):
    """Create default admin user if none exists."""
    admin = User.query.filter_by(role="super_admin").first()
    if not admin:
        admin = User(
            username="arena_admin",
            email="admin@controlarena.local",
            role="super_admin",
            is_active=True,
        )
        admin.set_password("ChangeMe@2026!")
        db.session.add(admin)
        db.session.commit()
        app.logger.info("✅ Default admin user created: arena_admin")


def _configure_logging(app):
    """Configure structured logging."""
    log_level = os.getenv("LOG_LEVEL", "INFO")
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# ── Application Entry Point ──────────────────────────────────────────────
app = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=app.config.get("DEBUG", False),
    )
