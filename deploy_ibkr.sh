#!/usr/bin/env bash
# deploy_ibkr.sh — Deploy IB Gateway (Live + Paper + Sunday scheduler) on a GCP VM
#
# Run ON the VM (e.g. via the console's SSH-in-browser or Cloud Shell):
#   curl -sSL https://raw.githubusercontent.com/sireesh27/AiTrading-Options-TradeUI/master/deploy_ibkr.sh | bash
#
# The gateways' API ports (4001 live / 4002 paper) and VNC ports (5900 / 5901)
# are bound to 127.0.0.1 on the VM -- the TWS API socket is unauthenticated, so
# they are never exposed to the internet. Reach them through an SSH tunnel:
#   gcloud compute ssh <vm> --zone <zone> -- -L 4001:localhost:4001 -L 4002:localhost:4002
# No GCP firewall rules are needed.

set -euo pipefail

REPO_URL="https://github.com/sireesh27/AiTrading-Options-TradeUI.git"
APP_DIR="$HOME/AiTrading-Options-TradeUI"
COMPOSE_FILE="docker-compose-ibkr.yml"
MIN_RAM_MB=3500   # two gateways need ~4 GB; e2-small (2 GB) will OOM

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── 0. Resources ──────────────────────────────────────────────────────────────
RAM_MB=$(awk '/MemTotal/ {printf "%d", $2/1024}' /proc/meminfo)
if [ "$RAM_MB" -lt "$MIN_RAM_MB" ]; then
    error "This VM has ${RAM_MB} MB RAM; live + paper gateways need ~4 GB. Resize to e2-medium (4 GB, tight) or e2-standard-2 (8 GB, recommended) and re-run."
fi
info "RAM: ${RAM_MB} MB — OK"

# ── 1. Docker ────────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    info "Installing Docker..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq docker.io docker-compose-v2 git curl
    sudo systemctl enable --now docker
    sudo usermod -aG docker "$USER"
    info "Docker installed (group membership applies at your next login; using sudo for now)."
fi
# Use sudo until the docker group membership is active in this shell.
DOCKER="docker"
docker info &>/dev/null || DOCKER="sudo docker"
$DOCKER compose version &>/dev/null || error "docker compose plugin missing (apt install docker-compose-v2)"
info "Docker $($DOCKER --version | awk '{print $3}' | tr -d ',') ready."

# ── 2. Clone or update repo ──────────────────────────────────────────────────
if [ -d "$APP_DIR/.git" ]; then
    info "Repo exists — pulling latest..."
    git -C "$APP_DIR" pull --ff-only origin master
else
    git clone "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"

# ── 3. Credentials (.env, never committed) ───────────────────────────────────
if grep -qs '^IBKR_USERNAME=' .env 2>/dev/null; then
    warn ".env already has IBKR credentials — keeping it. Edit .env to change them."
else
    info "IBKR credentials (stored only in $APP_DIR/.env, chmod 600):"
    read -rp  "  LIVE username: " IBKR_USER
    read -rsp "  LIVE password: " IBKR_PASS; echo
    echo      "  Paper needs its OWN paper user (IB rejects the live login for paper):"
    echo      "  Client Portal -> Settings -> Account Settings -> Paper Trading Account"
    read -rp  "  PAPER username: " IBKR_PAPER_USER
    read -rsp "  PAPER password: " IBKR_PAPER_PASS; echo
    read -rsp "  VNC password (only used if you ever VNC in): " VNC_PASS; echo

    cat >> .env << ENVEOF
# --- IBKR Gateway (docker-compose-ibkr.yml) ---
IBKR_USERNAME=${IBKR_USER}
IBKR_PASSWORD=${IBKR_PASS}
IBKR_PAPER_USERNAME=${IBKR_PAPER_USER}
IBKR_PAPER_PASSWORD=${IBKR_PAPER_PASS}
VNC_PASSWORD=${VNC_PASS}
# backend on this VM connects to the local containers
IBKR_HOST=127.0.0.1
IBKR_PORT_LIVE=4001
IBKR_PORT_PAPER=4002
ENVEOF
    chmod 600 .env
    info ".env written."
fi

# ── 4. Pull & start (live, paper, Sunday 11 AM ET scheduler) ─────────────────
info "Pulling images..."
$DOCKER compose -f "$COMPOSE_FILE" pull -q
info "Starting containers..."
$DOCKER compose -f "$COMPOSE_FILE" up -d
sleep 20
$DOCKER compose -f "$COMPOSE_FILE" ps

echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  IB Gateway containers started${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}NOW:${NC} the LIVE login sends an IB Key push to your phone — approve it."
echo "  Watch it:   $DOCKER logs -f ib-gateway-live | grep -E 'Second Factor|Login has completed'"
echo "  Paper logs in by itself (no 2FA)."
echo ""
echo "Schedule (America/New_York): nightly restart 11:45 PM (no login);"
echo "  weekly re-login Sunday 11:00 AM (one IB Key tap for live)."
echo ""
echo "Ports are bound to 127.0.0.1 on this VM. From your PC, tunnel them:"
echo "  gcloud compute ssh \$(hostname) --zone <zone> -- -L 4001:localhost:4001 -L 4002:localhost:4002"
echo "  then run the backend locally with IBKR_HOST=127.0.0.1 — or run it here:"
echo "  cd $APP_DIR && pip install -r requirements.txt && python backend_server.py"
echo ""
echo "  Logs:   $DOCKER compose -f $COMPOSE_FILE logs -f"
echo "  Stop:   $DOCKER compose -f $COMPOSE_FILE down"
