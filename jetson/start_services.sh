#!/bin/bash

# =============================================================================
# Clarity+ Microservices Launcher
# =============================================================================
# Activates the venv, installs requirements, then starts all services.
# Supports Mac (x86_64/arm64) and Jetson Nano (aarch64).

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "  Clarity+ Microservices"
echo "=========================================="

# ── Detect Jetson ─────────────────────────────────────────────────────
IS_JETSON=false
if [ -f /etc/nv_tegra_release ] 2>/dev/null || [ "$(uname -m)" = "aarch64" ]; then
    IS_JETSON=true
fi

# ── Create venv if missing ────────────────────────────────────────────
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create venv. Install python3-venv: sudo apt install python3-venv"
        exit 1
    fi
fi

# ── Activate virtual environment ──────────────────────────────────────
echo "Activating virtual environment..."
source venv/bin/activate

# ── Choose requirements file ──────────────────────────────────────────
REQ_FILE="requirements.txt"
if [ "$IS_JETSON" = true ] && [ -f "requirements-jetson.txt" ]; then
    REQ_FILE="requirements-jetson.txt"
    echo "Jetson detected: using requirements-jetson.txt"
    echo "  (PyTorch must be installed from NVIDIA wheels first. See JETSON.md)"
fi

# ── Install requirements ──────────────────────────────────────────────
echo "Installing requirements from $REQ_FILE..."
pip install -q -r "$REQ_FILE"
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install requirements."
    if [ "$IS_JETSON" = true ]; then
        echo "  On Jetson: install PyTorch from NVIDIA first. See JETSON.md"
    fi
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

# Check which services started successfully (lsof or ss fallback for Jetson)
echo ""
echo "Service status:"
_port_listening() {
    if command -v lsof >/dev/null 2>&1; then
        lsof -i :"$1" -sTCP:LISTEN >/dev/null 2>&1
    else
        ss -tlnp 2>/dev/null | grep -q ":$1 "
    fi
}
for port in 8002 8003 8004 8005 8006; do
    if _port_listening "$port"; then
        echo "  ✓ Port $port - running"
    else
        echo "  ✗ Port $port - FAILED (check services/*/service.log)"
    fi
done

# ── Start Orchestrator (foreground) ───────────────────────────────────
echo ""
echo "Starting Orchestrator (Port 8001)..."
python3 main.py
