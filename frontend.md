# Frontend (React SPA)

## 1. Overview
The user interface is a React SPA displayed via Chromium in Kiosk Mode on a 24" 1080p monitor. It provides real-time visual feedback and long-term wellness trends.

## 2. Technical Stack
- **Framework:** React 18.2 + TypeScript
- **State Management:** React Context API
- **Styling:** Tailwind CSS or styled-components (High contrast for mirror visibility)
- **Charts:** Chart.js or Recharts for history trends

## 3. UI/UX Flow

### A. Idle / Attract Mode
- **Feature:** Simple clock and "Approach to Start" message
- **Trigger:** Wake up on motion or face detection signal from Orchestrator

### B. Live Analysis View
- **Layout:** Real-time metrics overlays
- **Metrics:**
  - Circular "Wellness Score" (0-100)
  - Skin score with acne/wrinkle highlights
  - Posture skeleton (Green/Yellow/Red)
  - Eye strain alerts (e.g., "Blink more often!")

### C. User Enrollment
- **Logic:** Multi-step wizard to enroll a new face
- **Consent:** Explicit opt-in for local data storage

### D. History Dashboard
- **Trends:** 7-day and 30-day health progress charts
- **Badges:** Display earned streaks and achievements

## 4. Kiosk Mode Configuration
- **Environment:** Run in Chromium with flags:
  ```
  --kiosk --incognito --disable-pinch --overscroll-history-navigation=0
  ```
- **Interactions:** Support touch or placeholder comments for future Hand Gestures

## 5. Docker Integration
See [docker.md](file:///Users/akamdhillon/capstone/docker.md) for full container configuration.

### Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `REACT_APP_API_URL` | `http://localhost:8000` | Backend API endpoint |

### Container Details
- **Port:** 3000
- **Depends On:** `api-gateway` (must start first)

