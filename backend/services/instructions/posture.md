# Posture Analysis — Dashboard Integration Instructions

## Overview

Posture runs in the frontend (MediaPipe Pose Landmarker). Results are saved via `POST /api/posture/results`.

## Storage

- **File:** `backend/data/posture_results.json`
- **Format:** Array of `{ user_id?, score, status, neck_angle, torso_angle, ... }`

## Implementation Steps

1. ✅ Already implemented: `POST /api/posture/results` accepts `user_id`
2. ✅ Already implemented: `GET /api/posture/results?user_id=` filters by user
3. ✅ Frontend: `PostureView` passes `currentUser?.id` when saving
4. Dashboard: Pass `currentUser?.id` to `getPostureResults()` — already done
