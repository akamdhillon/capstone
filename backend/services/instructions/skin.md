# Skin Analysis — Dashboard Integration Instructions

## Overview

Skin analysis runs via the Jetson skin service. Results flow: frontend → backend `/api/debug/skin` → Jetson orchestrator → skin service.

## Storage

- **File:** `backend/data/skin_results.json`
- **Format:** Array of `{ user_id?, score, details?, timestamp }`

## Implementation Steps

1. Add `POST /api/skin/results` to save skin results (mirror posture pattern)
2. Add `GET /api/skin/results?user_id=` to fetch user's skin history
3. Frontend: Call save endpoint after `SkinCheckView` or `AnalysisView` returns skin data
4. Extend `GET /api/summary` to include `latest_skin` from skin_results (filtered by user_id)
5. Dashboard: Display `summary.latest_skin?.score` in Skin ScoreCard
