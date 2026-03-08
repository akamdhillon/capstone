# Clarity+ Smart Mirror

A real-time wellness monitoring system that uses computer vision and machine learning to analyze skin health, posture, eye strain, and thermal data, all displayed on a smart mirror interface.

## Prerequisites

### Git LFS (Required for skin analysis model)

The skin analysis model checkpoint (`best_model.pth`, ~54MB) is stored in Git LFS. You must install Git LFS before cloning or pulling this repo, otherwise the model file will be a placeholder and skin analysis will fall back to a random stub.

**macOS:**
```bash
brew install git-lfs
git lfs install
```

**Windows:**
Download and run the installer from [git-lfs.github.com](https://git-lfs.github.com), then:
```bash
git lfs install
```

After installing, pull the model file if you already have the repo cloned:
```bash
git lfs pull
```

---

## Testing

# Backend
```bash
cd backend && python -m pytest tests/ -v
```

# Jetson
```bash
cd jetson && python -m pytest tests/ -v
```

# Frontend
```bash
cd frontend && npx vitest run
```

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

| Port | Service | Model/Library | Description |
|------|---------|---------------|-------------|
| 8001 | **Orchestrator** | FastAPI | Main entry point used by Backend to request analysis. |
| 8002 | Face Recognition | DeepFace (RetinaFace + FaceNet512) | Detect and identify users |
| 8003 | Skin Analysis | YOLOv8n (TensorRT) | Detect acne, wrinkles, dark spots |
| 8004 | Posture Detection | MediaPipe Pose | Calculate head tilt, slouch detection |
| 8005 | Eye Strain | EAR Algorithm + HSV Analysis | Blink rate, sclera redness |
| 8006 | Thermal | (Ghost Service) | Returns null when disabled |

## High-Level Interaction / System Design

### 1. Voice Pipeline (Hands-Free Control)
Always-on wake word engine on Raspberry Pi listening for "Hey Clarity" (e.g., Porcupine, Vosk, or similar).

When wake word fires:
- Unmutes mic.
- Opens WebSocket or streaming HTTP to backend for STT + LLM.

**STT service**
Could be Whisper (local) or cloud STT.
Streams audio → text and sends each user utterance to the backend orchestrator.

### 2. Backend Orchestrator Flow (Port 8000)
For each user interaction, the flow is as follows:

**Receive:**
- `user_text`
- `user_id` (if face recognition on 8002 has run)
- `display_name`
- `session_id`

**Call LLM with:**
- System prompt.
- Conversation history (light).
- Latest `user_text` + `user_id` context.

**Parse LLM JSON:**
- `assistant_message` → TTS → audio back to mirror speakers.
- `intent` + `actions` → internal router.

**For each action in actions:**
Map action to internal HTTP call:
- `run_posture_check` → Jetson Orchestrator (8001) → Posture (8004).
- `run_acne_check` → Jetson Orchestrator (8001) → Skin (8003).
- etc.

**When results return:**
- Store in SQLite.
- Call LLM again to "explain results" in user-friendly language (supply raw JSON + image URLs).
- Speak back via TTS.

### 3. FaceID + Personalization
Jetson 8002 (Face Recognition) continuously identifies user when in front of mirror.
- Backend keeps `current_user_id` in session.
- When wake word triggers, backend checks last `face_id` and confidence.
- Passes `user_id` and `display_name` into the LLM as context.
- LLM uses that to say "Hi [Name]…" and to choose correct DB rows for summaries.

### 4. Mode Examples
- **"Hey Clarity, check my posture."**
  - STT → LLM → JSON with intent: `POSTURE_CHECK`, actions: `[run_posture_check]`.
  - Backend calls posture service, waits, then calls LLM again with results for explanation.
- **"Hey Clarity, how’s my skin looking compared to last week?"**
  - LLM decides: `run_acne_check` (if fresh check) + `get_daily_summary` (for trends).
  - Backend sequences the calls and feeds combined results back into LLM.
---

## Testing the Complete Voice Orchestrator Pipeline

To test the complete "Hey Clarity check posture" voice-first pipeline:

### 1. Requirements

**Backend / Desktop:**
```bash
cd backend
pip install -r requirements.txt
# Ensure you have ffmpeg installed for Whisper:
# brew install ffmpeg
# Ensure you have ollama installed:
# curl -fsSL https://ollama.ai/install.sh | sh && ollama run llama3.2:3b
python main.py
```

**Raspberry Pi / Voice Client:**
```bash
pip install -r requirements.txt
export ELEVENLABS_API_KEY="your-eleven-labs-key"
export PICOVOICE_ACCESS_KEY="your-picovoice-key"

# Run the wake word loop
python pi_voice_client.py 
```

### 2. Integration Instructions

1. `backend/voice_orchestrator.py` listens correctly on `/voice/intent` via FastAPI router.
2. `backend/prompts/clarity.txt` holds the Llama system instruction set.
3. `pi_voice_client.py` captures STT (whisper) and converts the LLM text to TTS (Elevenlabs).
4. Jetson handles all HTTP request inputs from the backend!

### 3. Test Flow (cURL)

```bash
curl -X 'POST' \
  'http://localhost:8000/voice/intent' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "user_text": "check posture",
  "user_id": "nikunj",
  "display_name": "Nikunj",
  "history": []
}'
```

This request correctly touches Llama 3.2 3B and sequentially fires at Jetson port 8001!

| Port | Service           | Model/Library                      | Description                                           |
| ---- | ----------------- | ---------------------------------- | ----------------------------------------------------- |
| 8001 | **Orchestrator**  | FastAPI                            | Main entry point used by Backend to request analysis. |
| 8002 | Face Recognition  | DeepFace (RetinaFace + FaceNet512) | Detect and identify users                             |
| 8003 | Skin Analysis     | YOLOv8n (TensorRT)                 | Detect acne, wrinkles, dark spots                     |
| 8004 | Posture Detection | MediaPipe Pose                     | Calculate head tilt, slouch detection                 |
| 8005 | Eye Strain        | EAR Algorithm + HSV Analysis       | Blink rate, sclera redness                            |
| 8006 | Thermal           | (Ghost Service)                    | Returns null when disabled                            |
