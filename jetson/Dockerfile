# =============================================================================
# CLARITY+ JETSON ML INFERENCE - DOCKERFILE
# =============================================================================
# Target: NVIDIA Jetson Nano (ARM64 + CUDA)
# Base: L4T-ML image with TensorRT, CUDA, cuDNN pre-installed
# Optimized for real-time ML inference with GPU passthrough
# =============================================================================

# Use NVIDIA L4T base image with ML stack
# JetPack 4.6.1 compatible
FROM nvcr.io/nvidia/l4t-ml:r32.7.1-py3

# Environment configuration for NVIDIA runtime
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,video,utility
ENV CUDA_HOME=/usr/local/cuda
ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64:${LD_LIBRARY_PATH}
ENV PATH=/usr/local/cuda/bin:${PATH}

# Prevent interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install additional system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgstreamer1.0-0 \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    libgstreamer-plugins-base1.0-dev \
    v4l-utils \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements first for layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir --upgrade pip \
    && pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for models and test media
RUN mkdir -p /app/models /app/test_media /app/logs

# Expose service ports
# 8001: Face Recognition
# 8002: Skin Analysis
# 8003: Posture Detection
# 8004: Eye Strain
# 8005: Thermal (conditional)
EXPOSE 8001 8002 8003 8004 8005

# Health check for primary service
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run the ML inference server
CMD ["python3", "main.py"]
