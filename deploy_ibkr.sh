#!/usr/bin/env bash
# deploy_ibkr.sh — Deploy IB Gateway (Live + Paper) on GCP VM
# Run: bash deploy_ibkr.sh

set -euo pipefail

REPO_URL="https://github.com/sireesh27/AiTrading-Options-TradeUI.git"
APP_DIR="$HOME/AiTrading-Options-TradeUI"
COMPOSE_FILE="docker-compose-ibkr.yml"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── 1. Docker ────────────────────────────────────────────────────────────────
info "Checking Docker..."
if ! command -v docker &>/dev/null; then
    info "Installing Docker..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq docker.io docker-compose-plugin
    sudo systemctl enable --now docker
    sudo usermod -aG docker "$USER"
    info "Docker installed. Re-run this script to continue (group change requires new shell)."
    exec newgrp docker "$0"
else
    info "Docker $(docker --version | awk '{print $3}' | tr -d ',') already installed."
fi

if ! docker compose version &>/dev/null; then
    sudo apt-get install -y -qq docker-compose-plugin
fi

# ── 2. Clone or update repo ──────────────────────────────────────────────────
info "Setting up repo at $APP_DIR..."
if [ -d "$APP_DIR/.git" ]; then
    info "Repo exists — pulling latest..."
    git -C "$APP_DIR" pull origin master
else
    git clone "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"

# ── 3. Collect credentials ───────────────────────────────────────────────────
if [ -f ".env" ]; then
    warn ".env already exists. Skipping credential prompts. Delete .env to re-enter credentials."
else
    info "Enter IBKR credentials (stored only on this VM, never committed to git):"
    read -rp "  IBKR username: " IBKR_USER
    read -rsp "  IBKR password: " IBKR_PASS; echo
    read -rsp "  VNC password (for weekly re-auth via VNC viewer): " VNC_PASS; echo

    cat > .env << EOF
IBKR_USERNAME=${IBKR_USER}
IBKR_PASSWORD=${IBKR_PASS}
VNC_PASSWORD=${VNC_PASS}
EOF
    chmod 600 .env
    info ".env created with restricted permissions (600)."
fi

# ── 4. GCP firewall rules ─────────────────────────────────────────────────────
info "Checking GCP firewall rules..."
PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")

open_port() {
    local name=$1 ports=$2
    if gcloud compute firewall-rules describe "$name" --project="$PROJECT" &>/dev/null 2>&1; then
        info "Firewall rule '$name' already exists."
    else
        info "Creating firewall rule '$name' for ports $ports..."
        gcloud compute firewall-rules create "$name" \
            --project="$PROJECT" \
            --direction=INGRESS \
            --action=ALLOW \
            --rules="tcp:$ports" \
            --source-ranges=0.0.0.0/0 \
            --target-tags=ibkr-gateway \
            --description="IB Gateway: $ports" 2>/dev/null || warn "Could not create firewall rule (may need to do it in GCP Console)"
    fi
}

if [ -n "$PROJECT" ]; then
    open_port "allow-ibkr-api" "4001,4002"
    open_port "allow-ibkr-vnc" "5900,5901"
else
    warn "gcloud project not set — skipping firewall rules. Open ports 4001,4002,5900,5901 manually in GCP Console."
fi

# ── 5. Pull Docker images ─────────────────────────────────────────────────────
info "Pulling IB Gateway Docker images..."
docker pull ghcr.io/gnzsnz/ib-gateway:stable

# ── 6. Start containers ───────────────────────────────────────────────────────
info "Starting IB Gateway containers (live + paper)..."
docker compose -f "$COMPOSE_FILE" down 2>/dev/null || true
docker compose -f "$COMPOSE_FILE" up -d

# ── 7. Show status ────────────────────────────────────────────────────────────
info "Waiting 15s for containers to initialise..."
sleep 15
docker compose -f "$COMPOSE_FILE" ps

EXTERNAL_IP=$(curl -s -H "Metadata-Flavor: Google" \
    http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip \
    2>/dev/null || echo "<external-ip>")

echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  IB Gateway deployed successfully!${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo ""
echo "  Live API  → ${EXTERNAL_IP}:4001"
echo "  Paper API → ${EXTERNAL_IP}:4002"
echo ""
echo "  VNC (Live)  → vnc://${EXTERNAL_IP}:5900   password: see .env"
echo "  VNC (Paper) → vnc://${EXTERNAL_IP}:5901   password: see .env"
echo ""
echo -e "${YELLOW}Next step:${NC} Connect via VNC to complete the initial login."
echo "  After first login, IBC handles restarts automatically."
echo ""
echo "  View logs:  docker compose -f $COMPOSE_FILE logs -f"
echo "  Stop all:   docker compose -f $COMPOSE_FILE down"
echo ""
