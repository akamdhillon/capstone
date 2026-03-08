# Eye Strain Analysis — Dashboard Integration Instructions

## Overview

Eye strain analysis runs via the Jetson eyes service. Results flow: frontend → backend `/api/debug/eyes` → Jetson orchestrator → eyes service.

## Storage

- **File:** `backend/data/eye_results.json`
- **Format:** Array of `{ user_id?, score, details?: { blink_rate?, drowsiness? }, timestamp }`

## Implementation Steps

1. Add `POST /api/eyes/results` to save eye results (mirror posture pattern)
2. Add `GET /api/eyes/results?user_id=` to fetch user's eye history
3. Frontend: Call save endpoint after `EyeCheckView` or `AnalysisView` returns eye data
4. Extend `GET /api/summary` to include `latest_eye` from eye_results (filtered by user_id)
5. Dashboard: Display `summary.latest_eye?.score` in Eyes ScoreCard
