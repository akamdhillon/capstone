# Clarity+ on Jetson Nano

Setup guide for running the Clarity+ microservices stack on NVIDIA Jetson Nano.

## Prerequisites

- **JetPack 4.6+** (Ubuntu 18.04) or **JetPack 5.x/6.x** (Ubuntu 20.04/22.04)
- **Python 3.8+** (JetPack 5+ provides Python 3.8; JetPack 4.6 uses Python 3.6)
- **Git LFS** (for skin model checkpoint):
  ```bash
  sudo apt install git-lfs
  git lfs install
  git lfs pull
  ```

## 1. System Dependencies

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv python3-dev build-essential libopenblas-dev libjpeg-dev zlib1g-dev
pip3 install --upgrade pip
```

> **Note:** `python3-dev` (or `python3.8-dev`) provides Python.h, required to build insightface from source on aarch64 (no prebuilt wheel).

## 2. PyTorch (Jetson-Specific)

Standard `pip install torch` installs x86 binaries and will **not work** on Jetson. Install from NVIDIA's prebuilt wheels for your JetPack version.

### JetPack 5.x / 6.x

Check [NVIDIA's PyTorch for Jetson](https://docs.nvidia.com/deeplearning/frameworks/install-pytorch-jetson-platform/) for the current wheel URL. Example for JetPack 6.x:

```bash
# Example – replace with URL from NVIDIA docs for your JetPack
pip3 install torch torchvision
# Or from NVIDIA index:
# pip3 install --no-cache https://developer.download.nvidia.com/compute/redist/jp/vXX/pytorch/torch-*.whl
```

### JetPack 4.6 (Python 3.6)

Use a community wheel or build from source. Example from [PyTorch-Jetson-Nano](https://github.com/Qengineering/PyTorch-Jetson-Nano):

```bash
sudo apt install -y libopenblas-dev libopencv-dev python3-dev
pip3 install Cython
# Install wheel from Qengineering or similar for your exact JetPack
```

## 3. Create Venv and Install Requirements

```bash
cd jetson
python3 -m venv venv
source venv/bin/activate

# PyTorch must already be installed (step 2)
# Then install the rest:
pip install -r requirements-jetson.txt
```

## 4. Camera

- **USB webcam**: Use device `0` (default). Ensure `/dev/video0` exists.
- **Different device**: Set `CAMERA_DEVICE=1` (or 2, etc.) in `.env` if your camera is not `/dev/video0`.
- **CSI camera**: May need a GStreamer pipeline. Set `USE_GSTREAMER=true` in `.env` (pipeline support in `config.py` / `main.py` when implemented).

## 5. Ollama (Optional — LLM for Voice Assistant)

To run the voice assistant LLM on the Jetson instead of the Raspberry Pi:

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull the model (e.g. llama3.2:3b)
ollama pull llama3.2:3b

# Start Ollama (or run as a systemd service)
ollama serve
```

Ensure `.env` on the RPi has `OLLAMA_HOST=http://<JETSON_IP>:11434` so the backend connects to the Jetson's Ollama.

## 6. Run Services

```bash
./start_services.sh
```

The script detects Jetson and uses `requirements-jetson.txt` automatically. It will:

1. Create `venv` if missing
2. Activate venv and install requirements
3. Start Face (8002), Skin (8003), Posture (8004), Eyes (8005), Thermal (8006)
4. Start Orchestrator (8001) in the foreground

Press `Ctrl+C` to stop all services.

## 7. Troubleshooting

| Issue | Fix |
|-------|-----|
| `torch` import fails | Install PyTorch from NVIDIA wheels (step 2) before `requirements-jetson.txt` |
| Skin model not found | Run `git lfs pull` in the repo root |
| Camera fails | Check `ls /dev/video*` and camera permissions |
| Port in use | Stop other processes: `sudo lsof -i :8001` |
| Out of memory | Jetson Nano has 2–4GB RAM. Run fewer services or reduce resolution. |
