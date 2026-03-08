# Thermal Scan — Dashboard Integration Instructions

## Overview

Thermal scan runs via the Jetson thermal service. Currently a placeholder (hardware not connected). When implemented:

## Storage

- **File:** `backend/data/thermal_results.json`
- **Format:** Array of `{ user_id?, score, details?: { temperature_c?, ... }, timestamp }`

## Implementation Steps

1. Add `POST /api/thermal/results` to save thermal results (mirror posture pattern)
2. Add `GET /api/thermal/results?user_id=` to fetch user's thermal history
3. Frontend: Call save endpoint after full analysis or thermal scan returns data
4. Extend `GET /api/summary` to include `latest_thermal` from thermal_results (filtered by user_id)
5. Dashboard: Display `summary.latest_thermal?.score` in Thermal ScoreCard (remove `disabled` when data exists)
