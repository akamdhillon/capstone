# Clarity+

Mac-first smart mirror stack: **backend + frontend + local ML services + voice**.

## Quick start

```bash
./start_all.sh
```

## Where things run

- **Frontend**: `http://localhost:3000`
- **Backend API**: `http://localhost:8000` (docs at `http://localhost:8000/docs`)
- **Services orchestrator**: `http://localhost:8001`
- **Services**:
  - Face: `8002`
  - Skin: `8003`
  - Posture: `8004`
  - Eyes: `8005`

## Notes

- **Skin model requires Git LFS** (the checkpoint is stored via LFS). After cloning:

```bash
git lfs install
git lfs pull
```

- **Voice runs in the backend on Mac** (wake word + STT + intent + TTS). For quick manual triggering you can use the spacebar shortcut in the UI (it calls `POST /api/voice/trigger`).

