# Backend Orchestrator (Raspberry Pi)

## 1. Overview
The Orchestrator runs on a Raspberry Pi 4 (4GB). It acts as the API Gateway, manages the local SQLite database, and executes the business logic for scoring and gamification.

## 2. Technical Stack
- **Base OS:** Raspberry Pi OS (64-bit, Debian-based)
- **Language:** Python 3.10+
- **Framework:** FastAPI with Uvicorn
- **Database:** SQLite 3.40+
- **Communication:** REST Client (to Jetson) + WebSockets (to Frontend)

## 3. Core Services

### A. API Gateway (FastAPI)
- **Responsibility:** Single entry point for the Frontend
- **Logic:** When the UI requests an analysis, the Gateway must trigger parallel requests to the Jetson's ML services (Ports 8002-8006)
- **Security:** Use AES-256-GCM for encrypting face embeddings stored in the DB

### B. Wellness Scoring Engine
- **Logic:** Aggregate the JSON responses from the Jetson into a 0-100 score
- **Calculation:** Skin (30%), Posture (25%), Eye Strain (25%), Thermal (20%)
- **Thermal Toggle:** Include a global variable `THERMAL_HARDWARE_CONNECTED = False`. If False, redistribute the 20% weight proportionally to the other three categories

### C. Persistence & Storage (SQLite)
- **Tables:** `users`, `face_embeddings`, `daily_metrics`, `analysis_history`, `streaks`, `badges`
- **Privacy:** Implement an auto-pruning "Janitor Task" to delete raw image caches every 30 days

### D. Gamification Module
- **Streaks:** Increment consecutive days of use
- **Badges:** Award "Posture Pro" or "Consistent Glow" based on 7/30-day thresholds

## 4. Network Configuration
- **Static IP:** 192.168.10.1 (Ethernet interface)
- **Wi-Fi Interface:** Keep active for dependency updates and Git pushes; set as the default gateway for internet traffic

## 5. Docker Integration
See [docker.md](file:///Users/akamdhillon/capstone/docker.md) for full container configuration.

### Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `JETSON_IP` | `192.168.10.2` | Static IP for Jetson Nano |
| `THERMAL_ENABLED` | `false` | Enables thermal scoring |
| `DATABASE_URL` | `sqlite:///data/clarity.db` | Database connection |

### Adjusted Scoring Weights (When Thermal Disabled)
| Category | Normal | Without Thermal |
|----------|--------|-----------------|
| Skin | 30% | 40% |
| Posture | 25% | 35% |
| Eye Strain | 25% | 25% |
| Thermal | 20% | 0% |
