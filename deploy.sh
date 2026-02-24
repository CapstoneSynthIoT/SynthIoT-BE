#!/bin/bash

# =============================================================================
# SynthIoT Backend — VM Deployment Script
# =============================================================================
# Run this ONCE on a fresh Linux VM (Ubuntu 22.04+):
#   bash deploy.sh
#
# What it does:
#   1. Installs system-level dependencies
#   2. Creates a Python virtual environment
#   3. Installs all Python packages
#   4. Helps you configure your .env file
#   5. Runs Alembic database migrations
#   6. Installs & enables a systemd service (auto-starts on reboot)
# =============================================================================

set -e  # Exit immediately on any error

# --- Colour helpers ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Colour

info()    { echo -e "${BLUE}ℹ️  $1${NC}"; }
success() { echo -e "${GREEN}✅  $1${NC}"; }
warn()    { echo -e "${YELLOW}⚠️  $1${NC}"; }
error()   { echo -e "${RED}❌  $1${NC}"; exit 1; }
header()  { echo -e "\n${CYAN}══════════════════════════════════════════${NC}"; echo -e "${CYAN}  $1${NC}"; echo -e "${CYAN}══════════════════════════════════════════${NC}"; }

# --- Config ---
APP_DIR="$(cd "$(dirname "$0")" && pwd)"   # directory this script lives in
VENV_DIR="$HOME/synthiot_venv"
SERVICE_NAME="synthiot"
PYTHON_BIN="$VENV_DIR/bin/python"
UVICORN_BIN="$VENV_DIR/bin/uvicorn"
CURRENT_USER="$(whoami)"

header "SynthIoT Backend — VM Deployment"
info "App directory : $APP_DIR"
info "Virtual env   : $VENV_DIR"
info "Running as    : $CURRENT_USER"

# =============================================================================
# STEP 1 — System dependencies
# =============================================================================
header "Step 1: System Dependencies"

if command -v apt-get &>/dev/null; then
    info "Detected apt-based system. Installing system packages..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq \
        python3 python3-pip python3-venv python3-dev \
        libpq-dev postgresql-client \
        build-essential git curl
    success "System packages installed."
else
    warn "Non-apt system detected. Make sure these are installed manually:"
    warn "  python3, python3-venv, python3-dev, libpq-dev, build-essential"
fi

# =============================================================================
# STEP 2 — Python virtual environment
# =============================================================================
header "Step 2: Python Virtual Environment"

if [ -d "$VENV_DIR" ]; then
    success "Virtual environment already exists at $VENV_DIR"
else
    info "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    success "Virtual environment created at $VENV_DIR"
fi

# Activate venv for remainder of script
source "$VENV_DIR/bin/activate"
info "Python: $(python --version)"

# =============================================================================
# STEP 3 — Install Python dependencies
# =============================================================================
header "Step 3: Python Dependencies"

info "Upgrading pip..."
pip install --upgrade pip --quiet

info "Running install_requirements.sh inside the venv..."
cd "$APP_DIR"
bash install_requirements.sh

success "All Python packages installed."

# =============================================================================
# STEP 4 — Environment configuration
# =============================================================================
header "Step 4: Environment Configuration"

if [ -f "$APP_DIR/.env" ]; then
    success ".env file already exists — skipping creation."
else
    warn ".env file not found!"
    echo ""
    echo "  A template has been provided at: $APP_DIR/.env.example"
    echo ""
    echo "  Please fill in your values and save as .env:"
    echo ""
    echo "    cp $APP_DIR/.env.example $APP_DIR/.env"
    echo "    nano $APP_DIR/.env"
    echo ""

    read -rp "  Do you want to create .env from the template now? [Y/n] " answer
    answer="${answer:-Y}"
    if [[ "$answer" =~ ^[Yy]$ ]]; then
        cp "$APP_DIR/.env.example" "$APP_DIR/.env"
        success ".env created from template."
        echo ""
        warn "IMPORTANT: Open $APP_DIR/.env and fill in your API keys and DATABASE_URL before proceeding."
        echo ""
        read -rp "  Press ENTER when you are done editing .env..." _
    else
        error "Cannot continue without a .env file. Create it and re-run deploy.sh."
    fi
fi

# Quick validation — check the most critical keys are set
info "Validating required environment variables..."
source "$APP_DIR/.env"

MISSING_VARS=()
[ -z "$GROQ_API_KEY" ]    && MISSING_VARS+=("GROQ_API_KEY")
[ -z "$SERPER_API_KEY" ]  && MISSING_VARS+=("SERPER_API_KEY")
[ -z "$DATABASE_URL" ]    && MISSING_VARS+=("DATABASE_URL")

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    error "Missing required variables in .env: ${MISSING_VARS[*]}\nPlease fill them in and re-run deploy.sh."
fi
success "Environment variables look good."

# =============================================================================
# STEP 5 — Database migrations
# =============================================================================
header "Step 5: Database Migrations (Alembic)"

cd "$APP_DIR"
info "Running: alembic upgrade head"
"$VENV_DIR/bin/alembic" upgrade head
success "Database is up to date."

# =============================================================================
# STEP 6 — Systemd service
# =============================================================================
header "Step 6: Systemd Service"

SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

info "Installing $SERVICE_FILE ..."

# Fill in the template variables and write to /etc/systemd/system/
sudo bash -c "cat > $SERVICE_FILE" <<EOF
[Unit]
Description=SynthIoT Backend API
Documentation=https://github.com/your-org/SynthIoT-BE
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${UVICORN_BIN} main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=synthiot

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

success "Service installed and started."

# =============================================================================
# DONE
# =============================================================================
header "🎉  Deployment Complete!"
echo ""
echo -e "  ${GREEN}Service status:${NC}"
systemctl status "$SERVICE_NAME" --no-pager --lines=5
echo ""
echo -e "  ${CYAN}Useful commands:${NC}"
echo "    systemctl status $SERVICE_NAME          # check status"
echo "    journalctl -u $SERVICE_NAME -f          # live logs"
echo "    systemctl restart $SERVICE_NAME         # restart app"
echo "    systemctl stop $SERVICE_NAME            # stop app"
echo ""
echo -e "  ${CYAN}API is available at:${NC}"
echo "    http://$(hostname -I | awk '{print $1}'):8000"
echo "    http://$(hostname -I | awk '{print $1}'):8000/docs"
echo ""
