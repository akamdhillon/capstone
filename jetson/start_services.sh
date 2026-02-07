#!/bin/bash

# Kill any existing python processes related to our services
# Be careful with pkill -f python if other python scripts are running!
# We'll try to be more specific if possible, or just kill by port.
# But for now, let's just start them. If ports are in use, they'll fail.

echo "Starting Clarity+ Microservices..."

# Function to kill background processes on exit
cleanup() {
    echo "Stopping all services..."
    kill $(jobs -p)
    exit
}

trap cleanup SIGINT

# Start Microservices
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

# Wait a moment for services to spin up
sleep 2

# Start Orchestrator
echo "Starting Orchestrator (Port 8001)..."
python3 main.py
