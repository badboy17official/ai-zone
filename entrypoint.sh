#!/bin/bash
# ==============================================================================
# AI INTELLIGENCE ZONE — Control Arena
# Entrypoint Script — Initialize and start the application
# ==============================================================================

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║        AI INTELLIGENCE ZONE — Control Arena                 ║"
echo "║        Starting Application Server...                       ║"
echo "╚══════════════════════════════════════════════════════════════╝"

# ── Wait for Dependencies ─────────────────────────────────────────
wait_for_service() {
    local host=$1
    local port=$2
    local service=$3
    local retries=30

    echo "⏳ Waiting for $service ($host:$port)..."
    while ! nc -z "$host" "$port" 2>/dev/null; do
        retries=$((retries - 1))
        if [ $retries -le 0 ]; then
            echo "❌ $service not available after 30 attempts. Exiting."
            exit 1
        fi
        sleep 1
    done
    echo "✅ $service is ready."
}

# Wait for PostgreSQL if DATABASE_URL contains postgres
if echo "$DATABASE_URL" | grep -q "postgres"; then
    DB_HOST=$(echo "$DATABASE_URL" | sed -n 's/.*@\([^:]*\):.*/\1/p')
    DB_PORT=$(echo "$DATABASE_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    wait_for_service "${DB_HOST:-postgres}" "${DB_PORT:-5432}" "PostgreSQL"
fi

# Wait for Redis if REDIS_URL is set
if [ -n "$REDIS_URL" ]; then
    REDIS_HOST=$(echo "$REDIS_URL" | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
    REDIS_PORT=$(echo "$REDIS_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    wait_for_service "${REDIS_HOST:-redis}" "${REDIS_PORT:-6379}" "Redis"
fi

# ── Run Database Migrations ───────────────────────────────────────
echo "🔧 Initializing database..."
python -c "
from app import create_app
from models import db
app = create_app()
with app.app_context():
    db.create_all()
    print('   Tables created successfully.')
"

# ── Seed if requested ─────────────────────────────────────────────
if [ "$SEED_DATABASE" = "true" ]; then
    echo "🌱 Seeding database..."
    python seed.py
fi

# ── Start Application ────────────────────────────────────────────
echo ""
echo "🚀 Starting server on 0.0.0.0:5000..."
echo ""

exec "$@"
