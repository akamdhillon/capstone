#!/bin/bash

# =============================================================================
# Clarity+ — Start All Services (macOS compatible)
# =============================================================================
# Launches backend (8000), jetson ML services (8001-8006), and frontend (3000).
# Ctrl+C stops everything.

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

PIDS=()

cleanup() {
    echo ""
    echo -e "${BOLD}Stopping all services...${NC}"
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
    while [ $tries -lt 35 ]; do
        if lsof -i :"$port" -sTCP:LISTEN >/dev/null 2>&1; then
            echo -e "  ${GREEN}✓${NC} $name ready on port $port"
            return 0
        fi
        sleep 1
        tries=$((tries + 1))
    done
    echo -e "  ${RED}✗${NC} $name FAILED to start on port $port"
    return 1
}

# Kill anything already on our ports
echo -e "${BOLD}Cleaning up stale processes...${NC}"
for port in 8000 8001 8002 8003 8004 8005 8006 3000; do
    pid=$(lsof -ti :"$port" 2>/dev/null)
    if [ -n "$pid" ]; then
        echo "  Killing process on port $port (pid $pid)"
        kill -9 $pid 2>/dev/null
    fi
done
sleep 1

echo ""
echo -e "${BOLD}=========================================="
echo "        Clarity+ — Full System Start"
echo -e "==========================================${NC}"
echo ""

# ── 1. Backend (port 8000) ────────────────────────────────────────────
echo -e "${CYAN}[1/3] Backend (port 8000)${NC}"

cd "$ROOT_DIR/backend"

if [ ! -d "venv" ]; then
    echo "  Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

# Install backend Python deps only when requirements change
REQ_HASH_FILE=".venv_requirements_hash"
CURRENT_HASH="$(shasum requirements.txt 2>/dev/null | awk '{print $1}')"
SAVED_HASH="$(cat "$REQ_HASH_FILE" 2>/dev/null || echo "")"

if [ "$CURRENT_HASH" != "$SAVED_HASH" ] || [ -z "$SAVED_HASH" ]; then
    echo "  Installing backend Python dependencies..."
    pip install -r requirements.txt
    echo "$CURRENT_HASH" > "$REQ_HASH_FILE"
else
    echo "  Backend Python dependencies up to date."
fi

echo "  Starting backend..."
python3 main.py &
PIDS+=($!)

wait_for_port 8000 "Backend"
BACKEND_OK=$?
deactivate 2>/dev/null

# ── 2. Jetson ML Services (ports 8001-8006) ───────────────────────────
echo ""
echo -e "${CYAN}[2/3] Jetson ML Services (ports 8001-8006)${NC}"

cd "$ROOT_DIR/jetson"

if [ ! -d "venv" ]; then
    echo "  Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

# Install Jetson Python deps only when requirements change
REQ_HASH_FILE=".venv_requirements_hash"
CURRENT_HASH="$(shasum requirements.txt 2>/dev/null | awk '{print $1}')"
SAVED_HASH="$(cat "$REQ_HASH_FILE" 2>/dev/null || echo "")"

if [ "$CURRENT_HASH" != "$SAVED_HASH" ] || [ -z "$SAVED_HASH" ]; then
    echo "  Installing Jetson Python dependencies..."
    pip install -r requirements.txt
    echo "$CURRENT_HASH" > "$REQ_HASH_FILE"
else
    echo "  Jetson Python dependencies up to date."
fi

echo "  Starting microservices..."
python3 services/face/main.py &
PIDS+=($!)
python3 services/skin/main.py &
PIDS+=($!)
python3 services/posture/main.py &
PIDS+=($!)
python3 services/eyes/main.py &
PIDS+=($!)
python3 services/thermal/main.py &
PIDS+=($!)

JETSON_OK=0
wait_for_port 8002 "Face service"
[ $? -ne 0 ] && JETSON_OK=1
wait_for_port 8003 "Skin service"
[ $? -ne 0 ] && JETSON_OK=1
wait_for_port 8004 "Posture service"
[ $? -ne 0 ] && JETSON_OK=1
wait_for_port 8005 "Eyes service"
[ $? -ne 0 ] && JETSON_OK=1
wait_for_port 8006 "Thermal service"
[ $? -ne 0 ] && JETSON_OK=1

echo "  Starting orchestrator..."
python3 main.py &
PIDS+=($!)

wait_for_port 8001 "Orchestrator"
[ $? -ne 0 ] && JETSON_OK=1
deactivate 2>/dev/null

# ── 3. Frontend (port 3000) ───────────────────────────────────────────
echo ""
echo -e "${CYAN}[3/3] Frontend (port 3000)${NC}"

cd "$ROOT_DIR/frontend"

if [ ! -d "node_modules" ]; then
    echo "  Installing npm dependencies..."
    npm install
fi

echo "  Starting dev server..."
npm run dev &
PIDS+=($!)

wait_for_port 3000 "Frontend"
FRONTEND_OK=$?

# ── Summary ───────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}==========================================${NC}"

FAILED=0
[ "$BACKEND_OK" -ne 0 ] && FAILED=1
[ "$JETSON_OK" -ne 0 ] && FAILED=1
[ "$FRONTEND_OK" -ne 0 ] && FAILED=1

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}${BOLD}  All services running!${NC}"
else
    echo -e "${RED}${BOLD}  Some services failed to start. Check output above.${NC}"
fi

echo -e "${BOLD}==========================================${NC}"
echo ""
echo -e "  Frontend:     http://localhost:3000"
echo -e "  Backend API:  http://localhost:8000"
echo -e "  Backend docs: http://localhost:8000/docs"
echo -e "  Jetson:       http://localhost:8001"
echo ""
echo -e "${BOLD}  Press Ctrl+C to stop everything.${NC}"

wait
