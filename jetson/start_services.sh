#!/bin/bash

# =============================================================================
# Clarity+ Microservices Launcher
# =============================================================================
# Activates the venv, installs requirements, then starts all services.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "  Clarity+ Microservices"
echo "=========================================="

# ── Activate virtual environment ──────────────────────────────────────
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "ERROR: No venv found. Run 'python3 -m venv venv' first."
    exit 1
fi

# ── Install requirements ──────────────────────────────────────────────
echo "Installing requirements..."
pip install -q -r requirements.txt
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install requirements."
    exit 1
fi
echo "✓ Requirements installed"

# ── Cleanup on exit ───────────────────────────────────────────────────
cleanup() {
    echo ""
    echo "Stopping all services..."
    kill $(jobs -p) 2>/dev/null
    wait 2>/dev/null
    echo "All services stopped."
    exit
}

trap cleanup SIGINT SIGTERM

# ── Start Microservices ───────────────────────────────────────────────
echo ""
echo "Starting Face Service (Port 8002)..."
python3 services/face/main.py > services/face/service.log 2>&1 &

echo "Starting Skin Service (Port 8003)..."
python3 services/skin/main.py > services/skin/service.log 2>&1 &

echo "Starting Posture Service (Port 8004)..."
python3 services/posture/main.py > services/posture/service.log 2>&1 &

echo "Starting Eyes Service (Port 8005)..."
python3 services/eyes/main.py > services/eyes/service.log 2>&1 &

echo "Starting Thermal Service (Port 8006)..."
python3 services/thermal/main.py > services/thermal/service.log 2>&1 &

# Wait for services to spin up
echo ""
echo "Waiting for services to initialize..."
sleep 3

# Check which services started successfully
echo ""
echo "Service status:"
for port in 8002 8003 8004 8005 8006; do
    if lsof -i :$port -sTCP:LISTEN > /dev/null 2>&1; then
        echo "  ✓ Port $port - running"
    else
        echo "  ✗ Port $port - FAILED (check service.log)"
    fi
done

# ── Start Orchestrator (foreground) ───────────────────────────────────
echo ""
echo "Starting Orchestrator (Port 8001)..."
python3 main.py
