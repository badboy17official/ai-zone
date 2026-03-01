#!/bin/bash
# ==============================================================================
# AI INTELLIGENCE ZONE — Control Arena
# Quick Start Script — Local Development
# ==============================================================================

set -e

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     🧠 AI INTELLIGENCE ZONE — Control Arena                ║"
echo "║     Local Development Quick Start                          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Check Python ──────────────────────────────────────────────────
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

PYTHON=$(command -v python3)
PIP="$PYTHON -m pip"

echo "🐍 Using: $($PYTHON --version)"

# ── Create Virtual Environment ────────────────────────────────────
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    $PYTHON -m venv venv
fi

echo "🔌 Activating virtual environment..."
source venv/bin/activate

# ── Install Dependencies ─────────────────────────────────────────
echo "📥 Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q 2>/dev/null || {
    echo "⚠️  Some optional packages may have failed. Installing core deps..."
    pip install Flask Flask-SQLAlchemy Flask-Login Flask-WTF Flask-CORS \
                Flask-Limiter Flask-SocketIO PyJWT bcrypt jsonschema \
                python-dotenv gunicorn eventlet -q
}

# ── Create .env if missing ───────────────────────────────────────
if [ ! -f ".env" ]; then
    echo "📋 Creating .env from template..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        # Generate a random secret key
        SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
        sed -i "s/your-super-secret-key-change-this-in-production/$SECRET/" .env
        echo "   ✅ .env created with random secret key"
    else
        echo "   ⚠️  No .env.example found"
    fi
fi

# ── Seed Database ─────────────────────────────────────────────────
echo ""
read -p "🌱 Seed database with demo data? (y/N): " SEED_CHOICE
if [[ "$SEED_CHOICE" =~ ^[Yy]$ ]]; then
    echo "🌱 Seeding database..."
    python seed.py
fi

# ── Start Server ──────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  🚀 Starting AI INTELLIGENCE ZONE — Control Arena"
echo "  📍 Admin Dashboard: http://localhost:5000/admin/"
echo "  📍 API Health:      http://localhost:5000/api/health"
echo "  🔑 Login:           arena_admin / ChangeMe@2026!"
echo "════════════════════════════════════════════════════════════════"
echo ""

python app.py
