#!/bin/bash
# ============================================================
# IB Gateway Launcher — Live + Paper  (auto-login via IBC)
# ============================================================
# Live  → port 4001  (JtsLive config dir)
# Paper → port 4002  (JtsPaper config dir)
#
# Credentials are read from .env — never hardcoded.
#
# Usage:
#   ./start_ibgateway.sh          → start both
#   ./start_ibgateway.sh live     → start Live only
#   ./start_ibgateway.sh paper    → start Paper only
#   ./start_ibgateway.sh stop     → stop both
#   ./start_ibgateway.sh status   → connection status
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

# ── Paths ──────────────────────────────────────────────────
TWS_VERSION="10.45"
TWS_APP_PATH="/Users/godev/IBKRApps"   # symlink → /Volumes/OWC Express 1M2/Applications (no spaces)
IBC_PATH="$SCRIPT_DIR/ibc"

# Use space-free symlinks — ibcstart.sh's find/Java break on paths with spaces
LIVE_JTS="/Users/godev/JtsLive"    # symlink → /Volumes/OWC Express 1M2/JtsLive
PAPER_JTS="/Users/godev/JtsPaper"  # symlink → /Volumes/OWC Express 1M2/JtsPaper

LIVE_PORT=4001
PAPER_PORT=4002

# ── Colors ─────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# ── Load credentials from .env ─────────────────────────────
load_credentials() {
    if [ ! -f "$ENV_FILE" ]; then
        echo -e "${RED}[ERROR]${NC} .env file not found at $ENV_FILE"
        exit 1
    fi

    IBKR_USERNAME=$(grep -E '^IBKR_USERNAME=' "$ENV_FILE" | cut -d '=' -f2- | tr -d '"' | tr -d "'")
    IBKR_PASSWORD=$(grep -E '^IBKR_PASSWORD=' "$ENV_FILE" | cut -d '=' -f2- | tr -d '"' | tr -d "'")

    if [ -z "$IBKR_USERNAME" ] || [ -z "$IBKR_PASSWORD" ]; then
        echo -e "${RED}[ERROR]${NC} IBKR_USERNAME or IBKR_PASSWORD not set in .env"
        echo "  Add these lines to .env:"
        echo "    IBKR_USERNAME=your_username"
        echo "    IBKR_PASSWORD=your_password"
        exit 1
    fi
}

# ── Build temp IBC config with credentials injected ────────
build_ibc_config() {
    local MODE=$1        # live | paper
    local OUT="/tmp/ibc_config_${MODE}.ini"
    cp "$IBC_PATH/config.${MODE}.ini" "$OUT"
    sed -i '' "s/^IbLoginId=.*/IbLoginId=$IBKR_USERNAME/" "$OUT"
    sed -i '' "s/^IbPassword=.*/IbPassword=$IBKR_PASSWORD/" "$OUT"
    echo "$OUT"
}

# ── Helpers ────────────────────────────────────────────────
is_port_open() {
    nc -z 127.0.0.1 "$1" 2>/dev/null
}

is_running() {
    pgrep -f "JtsPaper\|JtsLive\|jtsConfigDir=$1" > /dev/null 2>&1
}

# ── Start one instance via ibcstart.sh ─────────────────────
start_gateway() {
    local MODE=$1        # live | paper
    local JTS_DIR=$2
    local PORT=$3

    if is_port_open "$PORT"; then
        echo -e "${YELLOW}[SKIP]${NC} IB Gateway $MODE already running on port $PORT"
        return
    fi

    echo -e "${BLUE}[START]${NC} Launching IB Gateway $MODE (port $PORT)..."

    local IBC_CONFIG
    IBC_CONFIG=$(build_ibc_config "$MODE")

    # Run ibcstart.sh directly (not via osascript Terminal window)
    # IBC_VRSN is required by ibcstart.sh for the banner
    IBC_VRSN="3.23.0" \
    "$IBC_PATH/scripts/ibcstart.sh" \
        "$TWS_VERSION" \
        --gateway \
        "--tws-path=$TWS_APP_PATH" \
        "--tws-settings-path=$JTS_DIR" \
        "--ibc-path=$IBC_PATH" \
        "--ibc-ini=$IBC_CONFIG" \
        "--mode=$MODE" \
        > "/tmp/ibgw_${MODE}.log" 2>&1 &

    local PID=$!
    echo -e "        PID: $PID | Log: /tmp/ibgw_${MODE}.log"

    # Wait up to 90s for port to open
    echo -n "        Waiting for port $PORT"
    for i in $(seq 1 90); do
        sleep 1
        if is_port_open "$PORT"; then
            echo -e " ${GREEN}✅ Ready!${NC}"
            rm -f "$IBC_CONFIG"   # credentials gone from disk
            return
        fi
        echo -n "."
    done

    echo -e " ${YELLOW}⏳ Not yet ready — check /tmp/ibgw_${MODE}.log${NC}"
    rm -f "$IBC_CONFIG"
}

# ── Stop one instance ───────────────────────────────────────
stop_gateway() {
    local MODE=$1
    local JTS_DIR=$2
    local PORT=$3

    # Kill by matching the settings path in the process args
    local DIR_NAME
    DIR_NAME=$(basename "$JTS_DIR")
    local PID
    PID=$(pgrep -f "$DIR_NAME" 2>/dev/null | head -1)

    if [ -n "$PID" ]; then
        echo -e "${RED}[STOP]${NC} Stopping IB Gateway $MODE (PID $PID)..."
        kill "$PID" 2>/dev/null
        sleep 1
        echo -e "        ${GREEN}Done.${NC}"
    else
        echo -e "${YELLOW}[SKIP]${NC} IB Gateway $MODE is not running"
    fi
}

# ── Status ─────────────────────────────────────────────────
check_status() {
    echo ""
    echo "═══════════════════════════════════════"
    echo "  IB Gateway Status"
    echo "═══════════════════════════════════════"

    if is_port_open $LIVE_PORT; then
        echo -e "  LIVE  (port $LIVE_PORT): ${GREEN}✅ Connected${NC}"
    elif pgrep -f "JtsLive" > /dev/null 2>&1; then
        echo -e "  LIVE  (port $LIVE_PORT): ${YELLOW}⏳ Starting / awaiting login${NC}"
    else
        echo -e "  LIVE  (port $LIVE_PORT): ${RED}❌ Not running${NC}"
    fi

    if is_port_open $PAPER_PORT; then
        echo -e "  PAPER (port $PAPER_PORT): ${GREEN}✅ Connected${NC}"
    elif pgrep -f "JtsPaper" > /dev/null 2>&1; then
        echo -e "  PAPER (port $PAPER_PORT): ${YELLOW}⏳ Starting / awaiting login${NC}"
    else
        echo -e "  PAPER (port $PAPER_PORT): ${RED}❌ Not running${NC}"
    fi

    echo "═══════════════════════════════════════"
    echo ""
}

# ── Main ───────────────────────────────────────────────────
MODE=${1:-both}

case "$MODE" in
    status)
        check_status
        ;;
    stop)
        echo ""
        echo "Stopping IB Gateway instances..."
        stop_gateway "live"  "$LIVE_JTS"  $LIVE_PORT
        stop_gateway "paper" "$PAPER_JTS" $PAPER_PORT
        echo ""
        ;;
    live)
        echo ""
        echo "═══════════════════════════════════════"
        echo "  IB Gateway — LIVE"
        echo "═══════════════════════════════════════"
        load_credentials
        start_gateway "live" "$LIVE_JTS" $LIVE_PORT
        check_status
        ;;
    paper)
        echo ""
        echo "═══════════════════════════════════════"
        echo "  IB Gateway — PAPER"
        echo "═══════════════════════════════════════"
        load_credentials
        start_gateway "paper" "$PAPER_JTS" $PAPER_PORT
        check_status
        ;;
    both|*)
        echo ""
        echo "═══════════════════════════════════════"
        echo "  IB Gateway — Live + Paper"
        echo "═══════════════════════════════════════"
        load_credentials
        start_gateway "live"  "$LIVE_JTS"  $LIVE_PORT
        echo ""
        start_gateway "paper" "$PAPER_JTS" $PAPER_PORT
        check_status
        ;;
esac
