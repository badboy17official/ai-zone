# ==============================================================================
# AI INTELLIGENCE ZONE — Control Arena
# Application Configuration Module
# ==============================================================================

import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class BaseConfig:
    """Base configuration shared across all environments."""

    # ── Flask Core ────────────────────────────────────────────────────────
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-change-me")

    # ── Database ──────────────────────────────────────────────────────────
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///control_arena.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": int(os.getenv("DB_POOL_SIZE", 10)),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", 5)),
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }

    # ── Redis ─────────────────────────────────────────────────────────────
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # ── Session ───────────────────────────────────────────────────────────
    SESSION_TYPE = "filesystem"
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(
        minutes=int(os.getenv("SESSION_LIFETIME_MINUTES", 120))
    )

    # ── Security ──────────────────────────────────────────────────────────
    WTF_CSRF_ENABLED = True
    JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", 8))
    ADMIN_REGISTRATION_CODE = os.getenv("ADMIN_REGISTRATION_CODE", "ARENA-ADMIN-2026")

    # ── Rate Limiting ─────────────────────────────────────────────────────
    RATELIMIT_DEFAULT = os.getenv("RATE_LIMIT_DEFAULT", "100/hour")
    RATELIMIT_STORAGE_URI = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    SUBMISSION_COOLDOWN_SECONDS = int(os.getenv("SUBMISSION_COOLDOWN_SECONDS", 10))

    # ── Competition ───────────────────────────────────────────────────────
    COMPETITION_NAME = os.getenv("COMPETITION_NAME", "AI Intelligence Zone — Control Arena")
    MAX_TEAMS = int(os.getenv("MAX_TEAMS", 50))
    MAX_TEAM_MEMBERS = int(os.getenv("MAX_TEAM_MEMBERS", 4))
    MAX_RETRIES_PER_MISSION = int(os.getenv("MAX_RETRIES_PER_MISSION", 20))

    # ── Scoring Weights ───────────────────────────────────────────────────
    WEIGHT_ACCURACY = float(os.getenv("WEIGHT_ACCURACY", 0.50))
    WEIGHT_SPEED = float(os.getenv("WEIGHT_SPEED", 0.20))
    WEIGHT_VALIDATION = float(os.getenv("WEIGHT_VALIDATION", 0.30))
    FIRST_BLOOD_BONUS = int(os.getenv("FIRST_BLOOD_BONUS", 50))
    PERFECT_PARSE_BONUS = int(os.getenv("PERFECT_PARSE_BONUS", 25))
    SPEED_DEMON_BONUS = int(os.getenv("SPEED_DEMON_BONUS", 30))
    CONSISTENCY_BONUS = int(os.getenv("CONSISTENCY_BONUS", 20))


class DevelopmentConfig(BaseConfig):
    """Development environment configuration."""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///control_arena_dev.db"
    )
    SQLALCHEMY_ENGINE_OPTIONS = {}  # SQLite doesn't use pool


class ProductionConfig(BaseConfig):
    """Production environment configuration."""
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"


class TestingConfig(BaseConfig):
    """Testing environment configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    WTF_CSRF_ENABLED = False


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config():
    """Return the appropriate config class based on FLASK_ENV."""
    env = os.getenv("FLASK_ENV", "development")
    return config_map.get(env, DevelopmentConfig)
