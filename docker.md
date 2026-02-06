# Docker Compose Configuration

## 1. Overview
This file allows you to launch the entire Clarity+ ecosystem on your local machine for development. It uses Environment Variables to handle the hardware toggles, such as disabling the Thermal sensor.

## 2. Configuration Logic
- **Networking:** Services communicate via a bridge network named `clarity-net`
- **Hardware Mocks:** For local development, the `jetson-ml` container should be configured to read from a local `.mp4` file instead of `/dev/video0`
- **Volumes:** Persists the SQLite database locally so your test users and streaks aren't lost on restart

## 3. The YAML Definition

```yaml
version: '3.8'

services:
  # ---------------------------------------------------------
  # RASPBERRY PI SERVICES (Orchestrator & UI)
  # ---------------------------------------------------------
  api-gateway:
    build: ./backend
    container_name: clarity_backend
    ports:
      - "8000:8000"
    environment:
      - JETSON_IP=192.168.10.2  # Static IP for Ethernet Bridge
      - THERMAL_ENABLED=false   # Toggle for thermal hardware
      - DATABASE_URL=sqlite:///data/clarity.db
    volumes:
      - ./backend/data:/app/data
    networks:
      - clarity-net
    restart: always

  frontend-ui:
    build: ./frontend
    container_name: clarity_ui
    ports:
      - "3000:3000"
    environment:
      - REACT_APP_API_URL=http://localhost:8000
    networks:
      - clarity-net
    depends_on:
      - api-gateway

  # ---------------------------------------------------------
  # JETSON NANO SERVICES (ML Inference)
  # ---------------------------------------------------------
  jetson-ml:
    build: ./jetson
    container_name: clarity_ml
    runtime: ${DOCKER_RUNTIME:-runc}  # Use 'nvidia' on the actual Jetson
    ports:
      - "8002-8006:8002-8006"
    environment:
      - ENABLE_THERMAL=false
      - DEV_MODE=true  # Tells OpenCV to use a video file instead of a camera
    volumes:
      - ./jetson/models:/app/models
      - ./test_media:/app/test_media
    networks:
      - clarity-net
    restart: always

networks:
  clarity-net:
    driver: bridge
```

## 4. Key Implementation Notes

### Environment Variable Reference

| Variable | Service | Default | Description |
|----------|---------|---------|-------------|
| `JETSON_IP` | api-gateway | `192.168.10.2` | Static IP for Jetson Nano on Ethernet bridge |
| `THERMAL_ENABLED` | api-gateway | `false` | Enables/disables thermal scoring in wellness calculation |
| `DATABASE_URL` | api-gateway | `sqlite:///data/clarity.db` | SQLite database connection string |
| `REACT_APP_API_URL` | frontend-ui | `http://localhost:8000` | Backend API endpoint for frontend |
| `ENABLE_THERMAL` | jetson-ml | `false` | Enables/disables thermal endpoint (Port 8005) |
| `DEV_MODE` | jetson-ml | `true` | Uses video file instead of camera for development |
| `DOCKER_RUNTIME` | jetson-ml | `runc` | Set to `nvidia` on actual Jetson hardware |

### Janitor Service (Background Task)
The `api-gateway` should implement a background task using FastAPI's `BackgroundTasks` or `apscheduler` to prune the `/app/data/images` folder every 30 days.

### Scoring Logic (Thermal Toggle)
When `THERMAL_ENABLED=false`, redistribute the 20% weight:

| Category | Normal Weight | Without Thermal |
|----------|---------------|-----------------|
| Skin Health | 30% | 40% |
| Posture | 25% | 35% |
| Eye Strain | 25% | 25% |
| Thermal | 20% | 0% (disabled) |

### Thermal Endpoint Handling
The `jetson-ml` service must use a conditional for the Port 8005 endpoint:

```python
if not ENABLE_THERMAL:
    return {"temp": null}
```

## 5. Development Commands

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Rebuild after code changes
docker-compose up -d --build

# Stop all services
docker-compose down

# Production mode on Jetson (with NVIDIA runtime)
DOCKER_RUNTIME=nvidia docker-compose up -d
```

## 6. Directory Structure

```
clarity/
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── data/
│   │   └── clarity.db
│   └── ...
├── frontend/
│   ├── Dockerfile
│   └── ...
├── jetson/
│   ├── Dockerfile
│   ├── models/
│   │   └── *.engine (TensorRT models)
│   └── ...
└── test_media/
    └── sample_video.mp4
```
