"""
BlinkTracker — stateful blink detection from EAR history.

Detects blinks by tracking EAR drops below threshold across frames.
Used only in video stream mode.
"""

EAR_BLINK_THRESHOLD = 0.20
EAR_CONSEC_FRAMES = 2  # frames EAR must be below threshold to count as blink


class BlinkTracker:
    def __init__(self):
        self.blink_count = 0
        self.consec_frames_below = 0
        self.ear_history: list[tuple[float, float]] = []  # (timestamp, ear)

    def update(self, ear: float, timestamp: float) -> None:
        self.ear_history.append((timestamp, ear))
        # Prune history older than 60 seconds
        cutoff = timestamp - 60.0
        self.ear_history = [(t, e) for t, e in self.ear_history if t >= cutoff]

        if ear < EAR_BLINK_THRESHOLD:
            self.consec_frames_below += 1
        else:
            if self.consec_frames_below >= EAR_CONSEC_FRAMES:
                self.blink_count += 1
            self.consec_frames_below = 0

    def blinks_per_minute(self) -> float | None:
        if len(self.ear_history) < 2:
            return None
        duration_seconds = self.ear_history[-1][0] - self.ear_history[0][0]
        if duration_seconds < 5:
            return None
        return round(self.blink_count / duration_seconds * 60, 1)
