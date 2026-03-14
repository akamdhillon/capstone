#!/bin/bash

# =============================================================================
# Clarity+ — Start Pi Services (Backend + Frontend)
# =============================================================================
# Launches backend (8000) and frontend (3000) on Raspberry Pi.
# Jetson runs start_services.sh separately for ML + voice.

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

PIDS=()

cleanup() {
    echo ""
    echo -e "${BOLD}Stopping Pi services...${NC}"
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null
    done
    sleep 1
    for pid in "${PIDS[@]}"; do
        kill -9 "$pid" 2>/dev/null
    done
    wait 2>/dev/null
    echo -e "${GREEN}All services stopped.${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

wait_for_port() {
    local port=$1
    local name=$2
    local tries=0
    while [ $tries -lt 30 ]; do
        if (command -v lsof >/dev/null 2>&1 && lsof -i :"$port" -sTCP:LISTEN >/dev/null 2>&1) || \
           (command -v ss >/dev/null 2>&1 && ss -tlnp 2>/dev/null | grep -q ":$port "); then
            echo -e "  ${GREEN}✓${NC} $name ready on port $port"
            return 0
        fi
        sleep 1
        tries=$((tries + 1))
    done
    echo -e "  ${RED}✗${NC} $name FAILED to start on port $port"
    return 1
}

echo ""
echo -e "${BOLD}=========================================="
echo "        Clarity+ Pi — Backend + Frontend"
echo -e "==========================================${NC}"
echo ""

# ── 1. Backend (port 8000) ────────────────────────────────────────────
echo -e "${CYAN}[1/2] Backend (port 8000)${NC}"
cd "$ROOT_DIR/backend"

if [ ! -d "venv" ]; then
    echo "  Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt
echo "  Starting backend..."
python3 main.py &
PIDS+=($!)
wait_for_port 8000 "Backend"
BACKEND_OK=$?
deactivate 2>/dev/null

# ── 2. Frontend (port 3000) ───────────────────────────────────────────
echo ""
echo -e "${CYAN}[2/2] Frontend (port 3000)${NC}"
cd "$ROOT_DIR/frontend"

if [ ! -d "node_modules" ]; then
    echo "  Installing npm dependencies..."
    npm install
fi

echo "  Starting frontend..."
if command -v pnpm >/dev/null 2>&1; then
    pnpm dev &
else
    npm run dev &
fi
PIDS+=($!)
wait_for_port 3000 "Frontend"
FRONTEND_OK=$?

# ── Summary ───────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}==========================================${NC}"
if [ "$BACKEND_OK" -eq 0 ] && [ "$FRONTEND_OK" -eq 0 ]; then
    echo -e "${GREEN}  Backend + Frontend running!${NC}"
else
    echo -e "${RED}  Some services failed to start.${NC}"
fi
echo -e "${BOLD}==========================================${NC}"
echo ""
echo -e "  Frontend:    http://localhost:3000"
echo -e "  Backend:     http://localhost:8000"
echo ""
echo -e "  Run Jetson:  jetson/start_services.sh (on Jetson)"
echo -e "  ${BOLD}Press Ctrl+C to stop.${NC}"
echo ""

wait
