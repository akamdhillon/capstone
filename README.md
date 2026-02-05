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

## Running on Raspberry Pi + Jetson Nano

### Network Setup

1. Connect RPi and Jetson via Ethernet cable
2. Configure static IPs:
   - **RPi**: `192.168.10.1`
   - **Jetson**: `192.168.10.2`

### Deploy on Raspberry Pi

```bash
# SSH into RPi
ssh pi@192.168.10.1

# Clone repository and navigate
cd ~/capstone

# Update .env for production
THERMAL_ENABLED=false
DEV_MODE=false
DOCKER_RUNTIME=runc

# Start services
docker-compose up -d api-gateway frontend-ui
```

### Deploy on Jetson Nano

```bash
# SSH into Jetson
ssh jetson@192.168.10.2

# Clone repository and navigate
cd ~/capstone

# Update .env for production with GPU
THERMAL_ENABLED=false
DEV_MODE=false
DOCKER_RUNTIME=nvidia

# Start ML services with NVIDIA runtime
DOCKER_RUNTIME=nvidia docker-compose up -d jetson-ml
```

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
