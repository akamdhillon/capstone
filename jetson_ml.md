# Jetson ML Service Layer

## 1. Overview
This service layer runs on an NVIDIA Jetson Nano (4GB) and is responsible for all real-time computer vision inference. It handles two 1080p camera streams, identifies users, and analyzes skin, posture, and eye strain.

## 2. Technical Stack
- **Base OS:** JetPack 4.6.x (Ubuntu 18.04)
- **Runtime:** Docker with nvidia-container-runtime
- **ML Frameworks:** TensorRT 8.x (Primary), ONNX Runtime 1.15
- **Vision Libraries:** OpenCV 4.8.x with GStreamer, MediaPipe 0.10.x

## 3. Service Definitions (Port Map: 8001-8005)
Each service must be containerized and exposed via a FastAPI wrapper.

### A. Camera Manager & Frame Buffer
- **Responsibility:** Capture MJPEG/H.264 streams from two USB cameras
- **Pipeline:** `v4l2src -> GStreamer -> OpenCV VideoCapture`
- **Output:** High-performance shared memory buffer or internal REST stream for downstream ML nodes

### B. Face Recognition Service (Port 8001)
- **Model:** DeepFace (RetinaFace for detection, FaceNet512 for embeddings)
- **Requirement:** < 100ms detection; > 95% accuracy
- **Logic:** Detect face -> Align landmarks -> Generate 512-dim embedding -> Return to Orchestrator for DB matching

### C. Skin Analysis Service (Port 8002)
- **Model:** YOLOv8n (Nano) optimized via TensorRT (FP16)
- **Target Classes:** Acne (inflammatory/non), Wrinkles, Dark Spots
- **Performance:** < 200ms inference time

### D. Posture Service (Port 8003)
- **Model:** MediaPipe Pose (BlazePose GHUM)
- **Logic:** Calculate head-forward angle and slouch detection (thoracic kyphosis) using 33 body keypoints
- **Note:** Add a comment placeholder for future MediaPipe Hands gesture control

### E. Eye Strain Service (Port 8004)
- **Metric 1:** Blink Rate via Eye Aspect Ratio (EAR)
- **Metric 2:** Sclera redness analysis via HSV color-space histograms

### F. Thermal Service Placeholder (Port 8005)
- **Status:** DISABLED by default
- **Logic:** Implement a FeatureToggle variable `ENABLE_THERMAL = False`
- **Structure:** Return a null or 0.0 value if disabled to avoid breaking the Orchestrator's wellness score logic

## 4. Hardware Optimization (Crucial for AI Agent)
- **TensorRT:** All models must be converted from `.onnx` to `.engine` for FP16 precision to hit the < 1s end-to-end latency target
- **Shared Memory:** Avoid excessive Base64 encoding between containers; use local socket streaming where possible

## 5. Network Configuration
- **Static IP:** 192.168.10.2 (via Ethernet to RPi)
- **Gateway:** Traffic routed to 192.168.10.1 (Raspberry Pi Orchestrator)

## 6. Docker Integration
See [docker.md](file:///Users/akamdhillon/capstone/docker.md) for full container configuration.

### Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_THERMAL` | `false` | Enables thermal endpoint (Port 8005) |
| `DEV_MODE` | `true` | Uses video file instead of camera |
| `DOCKER_RUNTIME` | `runc` | Set to `nvidia` on Jetson hardware |

### Development Mode
When `DEV_MODE=true`, the Camera Manager reads from `/app/test_media/sample_video.mp4` instead of `/dev/video0`.
