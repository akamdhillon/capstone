# Clarity+ Smart Mirror

A real-time wellness monitoring system that uses computer vision and machine learning to analyze skin health, posture, eye strain, and (optionally) thermal data—all displayed on a smart mirror interface.

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────┐
│                    CLARITY+ SYSTEM OVERVIEW                     │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────┐                    ┌─────────────────┐   │
│   │   Raspberry Pi  │◄──── Ethernet ────►│   Jetson Nano   │   │
│   │   192.168.10.1  │      Bridge        │   192.168.10.2  │   │
│   ├─────────────────┤                    ├─────────────────┤   │
│   │ • API Gateway   │                    │ • Face Recog.   │   │
│   │   (Port 8000)   │                    │   (Port 8001)   │   │
│   │ • Frontend UI   │   REST/JSON        │ • Skin Analysis │   │
│   │   (Port 3000)   │◄──────────────────►│   (Port 8002)   │   │
│   │ • SQLite DB     │                    │ • Posture       │   │
│   │ • Gamification  │                    │   (Port 8003)   │   │
│   └─────────────────┘                    │ • Eye Strain    │   │
│                                          │   (Port 8004)   │   │
│                                          │ • Thermal       │   │
│                                          │   (Port 8005)   │   │
│                                          └─────────────────┘   │
└────────────────────────────────────────────────────────────────┘
```

### Components

| Component | Location | Port(s) | Purpose |
|-----------|----------|---------|---------|
| **Backend Orchestrator** | `backend/` | 8000 | FastAPI gateway, SQLite DB, wellness scoring, gamification |
| **Jetson ML Services** | `jetson/` | 8001-8005 | Real-time ML inference (face, skin, posture, eyes, thermal) |
| **Frontend UI** | `frontend/` | 3000 | React SPA for real-time feedback and history trends |

---

## Prerequisites

### For Development (Mac/Linux)

- **Python 3.10+**
- **Node.js 20+** (for frontend)
- **Docker & Docker Compose** (optional, for containerized development)
- **A USB webcam** (or use DEV_MODE with video files)

### For Production (Raspberry Pi + Jetson)

- **Raspberry Pi 4** (4GB, running Raspberry Pi OS 64-bit)
- **NVIDIA Jetson Nano** (4GB, running JetPack 4.6.x)
- **Ethernet cable** (for RPi-Jetson bridge network)
- **USB cameras** (1080p recommended)

---

## Quick Start (Mac Development)

### 1. Clone and Setup

```bash
cd /Users/akamdhillon/capstone
```

### 2. Create Virtual Environment

```bash
# Backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Environment

Edit the `.env` file in the project root:

```bash
# Key settings for development
THERMAL_ENABLED=false      # No thermal sensor on Mac
DEV_MODE=true              # Use camera directly (no GStreamer)
DOCKER_RUNTIME=runc        # No NVIDIA runtime on Mac
```

### 4. Run Backend Locally

```bash
cd backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at:
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### 5. Run Jetson Services Locally (Partial Support)

> **Note**: Full ML inference requires NVIDIA GPU + TensorRT. On Mac, you can test the API structure but inference may be limited or require CPU fallback.

```bash
cd jetson
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run services (may have limited functionality on Mac)
python main.py
```

---

## Using Docker Compose

For a more complete development setup:

```bash
# Build and start all services
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

### Service URLs (Docker)

| Service | URL |
|---------|-----|
| Backend API | http://localhost:8000 |
| Frontend UI | http://localhost:3000 |
| Face Recognition | http://localhost:8001 |
| Skin Analysis | http://localhost:8002 |
| Posture Detection | http://localhost:8003 |
| Eye Strain | http://localhost:8004 |
| Thermal | http://localhost:8005 |

---

## Hardware Deployment Guide

This section covers the complete setup process for deploying Clarity+ on the Raspberry Pi 4 and Jetson Nano hardware.

---

### Jetson Nano Setup

The Jetson Nano runs all ML inference services (face recognition, skin analysis, posture detection, eye strain, and thermal).

#### 1. Network Configuration

Configure a static IP for the Ethernet interface to communicate with the Raspberry Pi.

```bash
# Edit network configuration
sudo nano /etc/network/interfaces
```

Add the following configuration:

```
auto eth0
iface eth0 inet static
    address 192.168.10.2
    netmask 255.255.255.0
    gateway 192.168.10.1
```

Alternatively, using NetworkManager:

```bash
# Create a static connection profile
sudo nmcli con add type ethernet con-name clarity-bridge ifname eth0 \
    ipv4.addresses 192.168.10.2/24 \
    ipv4.gateway 192.168.10.1 \
    ipv4.method manual

# Activate the connection
sudo nmcli con up clarity-bridge
```

Restart networking:

```bash
sudo systemctl restart networking
# or
sudo reboot
```

#### 2. Connect Ethernet to Raspberry Pi

- Use a standard Cat5e or Cat6 Ethernet cable
- Connect directly between Jetson and RPi (no switch needed)
- Verify connection after RPi is configured:
  ```bash
  ping 192.168.10.1
  ```

#### 3. Clone the Repository

```bash
cd ~
git clone https://github.com/yourusername/capstone.git
cd capstone
```

#### 4. Set Up Python Environment

```bash
cd ~/capstone/jetson

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

#### 5. Configure Environment Variables

```bash
cd ~/capstone
nano .env
```

Set the following for production:

```bash
THERMAL_ENABLED=false
DEV_MODE=false
DOCKER_RUNTIME=nvidia
JETSON_IP=192.168.10.2
RPI_IP=192.168.10.1
CAMERA_DEVICE=/dev/video0
MODEL_PRECISION=FP16
```

#### 6. Run the ML Services

**Option A: Without Docker (Direct Python)**

```bash
cd ~/capstone/jetson
source venv/bin/activate
python main.py
```

**Option B: With Docker (Recommended for Production)**

```bash
cd ~/capstone

# Pull/build and run with NVIDIA runtime
DOCKER_RUNTIME=nvidia docker-compose up -d jetson-ml

# View logs
docker-compose logs -f jetson-ml
```

#### 7. Verify Services Are Running

```bash
# Check all ML service health endpoints
curl http://localhost:8001/health  # Face Recognition
curl http://localhost:8002/health  # Skin Analysis
curl http://localhost:8003/health  # Posture Detection
curl http://localhost:8004/health  # Eye Strain
curl http://localhost:8005/health  # Thermal
```

---

### Raspberry Pi Setup

The Raspberry Pi runs the backend API gateway, SQLite database, and serves the React frontend.

#### 1. Network Configuration

Configure a static IP for the Ethernet interface.

```bash
# Using dhcpcd (default on Raspberry Pi OS)
sudo nano /etc/dhcpcd.conf
```

Add at the end of the file:

```
interface eth0
static ip_address=192.168.10.1/24
static routers=192.168.10.1
```

Restart networking:

```bash
sudo systemctl restart dhcpcd
# or
sudo reboot
```

#### 2. Connect Ethernet to Jetson Nano

- Use a standard Cat5e or Cat6 Ethernet cable
- Connect directly between RPi and Jetson
- After reboot, verify connection:
  ```bash
  ping 192.168.10.2
  ```

#### 3. Clone the Repository

```bash
cd ~
git clone https://github.com/yourusername/capstone.git
cd capstone
```

#### 4. Set Up Backend (Python)

```bash
cd ~/capstone/backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

#### 5. Set Up Frontend (Node.js)

Ensure Node.js 20+ is installed:

```bash
# Check Node version
node --version

# If not installed or outdated, install via NodeSource
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
```

Build the frontend:

```bash
cd ~/capstone/frontend

# Install dependencies
npm install

# Build for production
npm run build
```

#### 6. Configure Environment Variables

```bash
cd ~/capstone
nano .env
```

Set the following for production:

```bash
THERMAL_ENABLED=false
DEV_MODE=false
DOCKER_RUNTIME=runc
JETSON_IP=192.168.10.2
RPI_IP=192.168.10.1
LOG_LEVEL=INFO
NODE_ENV=production
```

#### 7. Run the Backend API

**Option A: Without Docker (Direct Python)**

```bash
cd ~/capstone/backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Option B: With Docker (Recommended for Production)**

```bash
cd ~/capstone

# Build and start backend + frontend containers
docker-compose up -d api-gateway frontend-ui

# View logs
docker-compose logs -f api-gateway
```

#### 8. Serve the Frontend

**Option A: Development server**

```bash
cd ~/capstone/frontend
npm run dev -- --host 0.0.0.0
```

**Option B: Production (with nginx or Docker)**

The Docker Compose setup serves the frontend at port 3000.

#### 9. Verify Everything is Running

```bash
# Check backend API
curl http://localhost:8000/health

# Check frontend is accessible
curl http://localhost:3000

# Verify connection to Jetson ML services
curl http://192.168.10.2:8001/health
```

---

### Quick Deployment Checklist

| Step | Jetson Nano | Raspberry Pi |
|------|-------------|--------------|
| 1. Configure static IP | `192.168.10.2` | `192.168.10.1` |
| 2. Connect Ethernet | ← Cable → | ← Cable → |
| 3. Clone repo | `git clone ...` | `git clone ...` |
| 4. Setup venv | `python3 -m venv venv` | `python3 -m venv venv` |
| 5. Install deps | `pip install -r requirements.txt` | `pip install -r requirements.txt` |
| 6. Configure .env | `DOCKER_RUNTIME=nvidia` | `DOCKER_RUNTIME=runc` |
| 7. Start services | `docker-compose up -d jetson-ml` | `docker-compose up -d api-gateway frontend-ui` |
| 8. Verify health | `curl localhost:8001/health` | `curl localhost:8000/health` |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `THERMAL_ENABLED` | `false` | Enable thermal scoring (requires hardware) |
| `DEV_MODE` | `false` | Use video file instead of live camera |
| `DOCKER_RUNTIME` | `runc` | Set to `nvidia` on Jetson for GPU |
| `JETSON_IP` | `192.168.10.2` | Jetson Nano IP address |
| `RPI_IP` | `192.168.10.1` | Raspberry Pi IP address |
| `CAMERA_DEVICE` | `/dev/video0` | Camera device path |
| `MODEL_PRECISION` | `FP16` | TensorRT precision (FP16/FP32) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## Project Structure

```
capstone/
├── backend/                 # Raspberry Pi Backend (FastAPI)
│   ├── config.py           # Configuration & weights
│   ├── main.py             # Application entry point
│   ├── database/           # SQLite models & connection
│   ├── routes/             # API endpoints
│   ├── services/           # Business logic (wellness scoring)
│   └── tasks/              # Background tasks (janitor)
│
├── jetson/                  # Jetson ML Services
│   ├── config.py           # ML configuration
│   ├── main.py             # Multi-service launcher (ports 8001-8005)
│   ├── routers/            # API endpoints per service
│   ├── services/           # ML inference logic
│   └── utils/              # Helper utilities
│
├── frontend/                # React Frontend (Kiosk Mode)
│   └── Dockerfile          # Build configuration
│
├── docker-compose.yml       # Container orchestration
├── .env                     # Environment configuration
└── *.md                     # Documentation files
```

---

## ML Services Description

| Port | Service | Model/Library | Description |
|------|---------|---------------|-------------|
| 8001 | Face Recognition | DeepFace (RetinaFace + FaceNet512) | Detect and identify users |
| 8002 | Skin Analysis | YOLOv8n (TensorRT) | Detect acne, wrinkles, dark spots |
| 8003 | Posture Detection | MediaPipe Pose | Calculate head tilt, slouch detection |
| 8004 | Eye Strain | EAR Algorithm + HSV Analysis | Blink rate, sclera redness |
| 8005 | Thermal | (Ghost Service) | Returns null when disabled |

---

## Wellness Scoring Formula

The overall wellness score (0-100) is calculated using weighted categories:

### With Thermal Hardware
| Category | Weight |
|----------|--------|
| Skin Health | 30% |
| Posture | 25% |
| Eye Strain | 25% |
| Thermal | 20% |

### Without Thermal Hardware (Default)
| Category | Weight |
|----------|--------|
| Skin Health | 40% |
| Posture | 35% |
| Eye Strain | 25% |

---

## API Endpoints

### Backend (Port 8000)

```
GET  /health              # Health check
GET  /api/users           # List users
POST /api/users           # Create user
GET  /api/analysis        # Get analysis history
POST /api/analysis        # Trigger new analysis
```

### Jetson ML Services

```
# All services respond to:
GET  /health              # Health check
POST /analyze             # Analyze image frame
```

---

## Development Workflow

1. **Develop on Mac**: Edit code, test API structure locally
2. **Test with Docker**: Use `docker-compose` for integration testing
3. **Deploy to Hardware**: Push changes, deploy on RPi/Jetson
4. **Verify with Camera**: Test with live USB camera feed

### Testing API Endpoints

```bash
# Check backend health
curl http://localhost:8000/health

# Check Jetson services (when running)
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8004/health
curl http://localhost:8005/health
```

---

## Troubleshooting

### Camera Not Working
- Ensure `DEV_MODE=false` for live camera
- Check camera device: `ls -la /dev/video*`
- On Jetson, ensure GStreamer is installed

### Services Not Connecting
- Verify network bridge: `ping 192.168.10.2` from RPi
- Check Docker network: `docker network ls`

### GPU Not Detected on Jetson
- Ensure `DOCKER_RUNTIME=nvidia` is set
- Verify NVIDIA runtime: `docker info | grep nvidia`

### Database Issues
- SQLite DB is at `backend/data/clarity.db`
- Delete to reset: `rm backend/data/clarity.db`

---

## Additional Documentation

- [Backend Details](backend.md)
- [Jetson ML Services](jetson_ml.md)
- [Frontend Details](frontend.md)
- [Docker Configuration](docker.md)
