# =============================================================================
# CLARITY+ BACKEND API GATEWAY - DOCKERFILE
# =============================================================================
# Target: Raspberry Pi 4 (ARM64)
# Base: Python 3.11 slim for minimal footprint
# =============================================================================

FROM python:3.11-slim-bookworm

# Prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd --gid 1000 clarity \
    && useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home clarity

# Copy requirements first for layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=clarity:clarity . .

# Create data directory for SQLite
RUN mkdir -p /app/data /app/logs \
    && chown -R clarity:clarity /app/data /app/logs

# Switch to non-root user
USER clarity

# Expose API port
EXPOSE 8000

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run FastAPI with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
