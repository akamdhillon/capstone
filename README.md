# Clarity+ Smart Mirror

A real-time wellness monitoring system that uses computer vision and machine learning to analyze skin health, posture, eye strain, and thermal data, all displayed on a smart mirror interface.

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
│   │   (Port 8000)   │                    │   (Port 8002)   │   │
│   │ • Frontend UI   │   REST/JSON        │ • Skin Analysis │   │
│   │   (Port 3000)   │◄──────────────────►│   (Port 8003)   │   │
│   │ • SQLite DB     │                    │ • Posture       │   │
│   │ • Gamification  │                    │   (Port 8004)   │   │
│   └─────────────────┘                    │ • Eye Strain    │   │
│                                          │   (Port 8005)   │   │
│                                          │ • Thermal       │   │
│                                          │   (Port 8006)   │   │
│                                          └─────────────────┘   │
└────────────────────────────────────────────────────────────────┘
```

### Components

| Component | Location | Port(s) | Purpose |
|-----------|----------|---------|---------|
| **Backend Orchestrator** | `backend/` | 8000 | FastAPI gateway, SQLite DB, wellness scoring, gamification |
| **Jetson ML Services** | `jetson/` | 8002-8006 | Real-time ML inference (face, skin, posture, eyes, thermal) |
| **Frontend UI** | `frontend/` | 3000 | React SPA for real-time feedback and history trends |

---



## Quick Start

### Clone and Setup

```bash
cd /Users/akamdhillon/capstone
```

### Backend

#### Create Virtual Environment

```bash
# Backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### Run Backend

```bash
cd backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at:
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### Nano Jetson Services

#### Create Virtual Environment

```bash
cd jetson
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run services (may have limited functionality on Mac)
python main.py
```



### Using Docker Compose


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



#### Network Configuration for Jetson Nano

Configure a static IP for the Ethernet interface to communicate with the Raspberry Pi.

```
auto eth0
iface eth0 inet static
    address 192.168.10.2
    netmask 255.255.255.0
    gateway 192.168.10.1
```

```bash
ping 192.168.10.1
```

```bash
cd ~/capstone/jetson
source venv/bin/activate
python main.py
```

## Set Up Frontend (Node.js)

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
| 8002 | Face Recognition | DeepFace (RetinaFace + FaceNet512) | Detect and identify users |
| 8003 | Skin Analysis | YOLOv8n (TensorRT) | Detect acne, wrinkles, dark spots |
| 8004 | Posture Detection | MediaPipe Pose | Calculate head tilt, slouch detection |
| 8005 | Eye Strain | EAR Algorithm + HSV Analysis | Blink rate, sclera redness |
| 8006 | Thermal | (Ghost Service) | Returns null when disabled |

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
