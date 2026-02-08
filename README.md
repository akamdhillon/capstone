# Clarity+ Smart Mirror

A real-time wellness monitoring system that uses computer vision and machine learning to analyze skin health, posture, eye strain, and thermal data, all displayed on a smart mirror interface.

## Quick Start (Local Mac Development)

### 1. Backend (Orchestrator)

Runs on Port **8000**.

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

### 2. Jetson Services (Mocked/Live)

The main Jetson orchestrator runs on Port **8001**.
It attempts to connect to microservices on ports **8002-8006**.

**To run everything locally:**

```bash
cd jetson
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run the startup script (Launches all microservices + orchestrator)
./start_services.sh
```

> **Note**: If on Mac, the camera will default to your webcam.

### 3. Frontend

Runs on Port **3000**.

```bash
cd frontend
pnpm install
pnpm dev
```

**Services**:

- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend: [http://localhost:8000](http://localhost:8000)
- Jetson Orchestrator: [http://localhost:8001](http://localhost:8001)

---

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
27: └────────────────────────────────────────────────────────────────┘
```

### Components

| Component                | Location      | Port(s)   | Purpose                                                     |
| ------------------------ | ------------- | --------- | ----------------------------------------------------------- |
| **Backend Orchestrator** | \`backend/\`  | 8000      | FastAPI gateway, SQLite DB, wellness scoring, gamification  |
| **Jetson ML Services**   | \`jetson/\`   | 8001-8006 | Real-time ML inference (face, skin, posture, eyes, thermal) |
| **Frontend UI**          | \`frontend/\` | 3000      | React SPA for real-time feedback and history trends         |

## ML Services Description

| Port | Service           | Model/Library                      | Description                                           |
| ---- | ----------------- | ---------------------------------- | ----------------------------------------------------- |
| 8001 | **Orchestrator**  | FastAPI                            | Main entry point used by Backend to request analysis. |
| 8002 | Face Recognition  | DeepFace (RetinaFace + FaceNet512) | Detect and identify users                             |
| 8003 | Skin Analysis     | YOLOv8n (TensorRT)                 | Detect acne, wrinkles, dark spots                     |
| 8004 | Posture Detection | MediaPipe Pose                     | Calculate head tilt, slouch detection                 |
| 8005 | Eye Strain        | EAR Algorithm + HSV Analysis       | Blink rate, sclera redness                            |
| 8006 | Thermal           | (Ghost Service)                    | Returns null when disabled                            |
