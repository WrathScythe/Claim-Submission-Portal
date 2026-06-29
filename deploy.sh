#!/bin/bash
# =============================================================
# Claim Submission Portal - Deployment Script (no Docker)
# =============================================================
# Prerequisites:
#   - Python 3.9+
#   - PostgreSQL 12+
#   - pip
# =============================================================

set -e

# ---------- Configuration ----------
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$APP_DIR/venv"
DB_NAME="claimdb"
DB_USER="claimuser"
DB_PASS="claimpass"
DB_HOST="localhost"
DB_PORT="5432"
APP_HOST="0.0.0.0"
APP_PORT="5000"
SECRET_KEY="change-this-to-a-random-secret-key-$(date +%s)"

# ---------- Colours for output ----------
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No colour

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ---------- Step 1: Check prerequisites ----------
info "Checking prerequisites..."

command -v python3 >/dev/null 2>&1 || { error "python3 is not installed. Please install Python 3.9+."; exit 1; }
command -v psql    >/dev/null 2>&1 || { error "psql is not installed. Please install PostgreSQL."; exit 1; }

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
info "Python version: $PYTHON_VERSION"

# ---------- Step 2: Create PostgreSQL database and user ----------
info "Setting up PostgreSQL database and user..."

# Prompt for PostgreSQL superuser credentials
read -rp "Enter PostgreSQL superuser name [postgres]: " PG_SUPERUSER
PG_SUPERUSER="${PG_SUPERUSER:-postgres}"

export PGPASSWORD=""
read -rsp "Enter password for '$PG_SUPERUSER' (press Enter if none): " PG_SUPERPASS
echo ""
export PGPASSWORD="$PG_SUPERPASS"

# Create user if not exists
psql -h "$DB_HOST" -p "$DB_PORT" -U "$PG_SUPERUSER" -tc \
    "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1 || \
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$PG_SUPERUSER" -c \
    "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';" 2>/dev/null && \
    info "Database user '$DB_USER' ready."

# Create database if not exists
psql -h "$DB_HOST" -p "$DB_PORT" -U "$PG_SUPERUSER" -tc \
    "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 || \
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$PG_SUPERUSER" -c \
    "CREATE DATABASE $DB_NAME OWNER $DB_USER;" 2>/dev/null && \
    info "Database '$DB_NAME' ready."

unset PGPASSWORD

# ---------- Step 3: Set up Python virtual environment ----------
info "Setting up Python virtual environment..."

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    info "Virtual environment created at $VENV_DIR"
else
    info "Virtual environment already exists at $VENV_DIR"
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# ---------- Step 4: Install Python dependencies ----------
info "Installing Python dependencies..."
pip install --upgrade pip -q
pip install -r "$APP_DIR/requirements.txt" -q
info "Dependencies installed."

# ---------- Step 5: Configure environment ----------
export DATABASE_URL="postgresql://$DB_USER:$DB_PASS@$DB_HOST:$DB_PORT/$DB_NAME"
export SECRET_KEY="$SECRET_KEY"
export FLASK_APP="app.py"

info "Environment configured:"
echo "  DATABASE_URL = $DATABASE_URL"
echo "  SECRET_KEY   = [set]"
echo "  APP_HOST     = $APP_HOST"
echo "  APP_PORT     = $APP_PORT"

# ---------- Step 6: Initialise database ----------
info "Initialising database (creating tables and seed data)..."
cd "$APP_DIR"
python3 -c "
from app import app, init_database
with app.app_context():
    init_database()
    print('Database tables and seed data created successfully.')
"
info "Database initialised."

# ---------- Step 7: Start the application ----------
info "Starting the Claim Submission Portal..."
info "Access the application at: http://localhost:$APP_PORT"
info ""
info "Demo credentials:"
info "  Staff user:    staff_user  / staff_pass"
info "  OIC admin:     oic_admin   / oic_admin_pass"
info ""
info "Press Ctrl+C to stop the server."
echo ""

cd "$APP_DIR"
gunicorn --bind "$APP_HOST:$APP_PORT" --workers 2 --reload app:app
