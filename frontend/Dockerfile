# =============================================================================
# CLARITY+ FRONTEND - DOCKERFILE
# =============================================================================
# Target: Raspberry Pi 4 (ARM64)
# Base: Node 20 Alpine for minimal footprint
# Multi-stage build for optimized production image
# =============================================================================

# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production=false

# Copy source code
COPY . .

# Build production bundle
RUN npm run build

# Stage 2: Production
FROM node:20-alpine AS production

WORKDIR /app

# Install serve for static file hosting
RUN npm install -g serve

# Create non-root user
RUN addgroup -g 1000 clarity \
    && adduser -u 1000 -G clarity -s /bin/sh -D clarity

# Copy built assets from builder
COPY --from=builder --chown=clarity:clarity /app/dist ./dist

# Switch to non-root user
USER clarity

# Expose frontend port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000 || exit 1

# Serve static files
CMD ["serve", "-s", "dist", "-l", "3000"]
