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

- **Ollama is required** (LLM + voice responses). Install it first:

`https://ollama.com/download`

- The backend will auto-download the **Vosk** STT model on first run.
- The posture service auto-downloads the **MediaPipe pose landmarker** model on first run.

- By default, `start_all.sh` runs a small curl smoke test at the end. Disable it with:

`SKIP_SMOKE_TEST=1 ./start_all.sh`

- **Voice runs in the backend on Mac** (wake word + STT + intent + TTS). For quick manual triggering you can use the spacebar shortcut in the UI (it calls `POST /api/voice/trigger`).

## Troubleshooting

- If ML services fail to start due to NumPy / binary ABI issues, re-run `./start_all.sh` (it re-installs service deps with a NumPy pin).
- If Ollama isn’t reachable, `./start_all.sh` will exit with instructions to install it.

