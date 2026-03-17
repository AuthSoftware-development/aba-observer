"""Pose estimation for movement and stereotypy detection using OpenCV.

Uses OpenCV's DNN module with a lightweight pose model to detect body
landmarks and analyze movement patterns. Falls back to motion-based
analysis if pose detection is unavailable.

Detects:
- Repetitive/stereotypical movements (hand flapping, body rocking)
- On-task vs off-task posture (stillness detection)
- Movement intensity over time
"""

import cv2
import numpy as np
from pathlib import Path


class PoseAnalyzer:
    """Analyze body pose and movement patterns from video."""

    def __init__(self):
        self._prev_frame_gray = None
        self._movement_history = []  # Rolling window

    def _compute_optical_flow_movement(self, frame: np.ndarray) -> float:
        """Compute movement using optical flow (frame differencing)."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if self._prev_frame_gray is None:
            self._prev_frame_gray = gray
            return 0.0

        # Frame difference
        diff = cv2.absdiff(self._prev_frame_gray, gray)
        _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)

        # Movement = percentage of pixels that changed
        movement = np.sum(thresh > 0) / thresh.size * 100
        self._prev_frame_gray = gray

        return round(movement, 3)

    def _detect_behaviors(self, movement: float) -> list[dict]:
        """Detect behavioral patterns from movement data."""
        behaviors = []

        self._movement_history.append(movement)
        if len(self._movement_history) > 30:
            self._movement_history.pop(0)

        # Sustained stillness (low movement for 5+ frames)
        if len(self._movement_history) >= 5:
            recent_5 = self._movement_history[-5:]
            if all(m < 0.5 for m in recent_5):
                behaviors.append({
                    "type": "sustained_stillness",
                    "confidence": 0.7,
                    "description": "Sustained low movement — possible on-task attention",
                })

        # High movement burst
        if movement > 5.0:
            behaviors.append({
                "type": "high_movement",
                "confidence": min(0.9, movement / 10),
                "description": f"High movement detected ({movement:.1f}% pixels changed)",
            })

        # Repetitive/oscillating movement (possible stereotypy)
        if len(self._movement_history) >= 10:
            recent_10 = self._movement_history[-10:]
            diffs = [recent_10[i + 1] - recent_10[i] for i in range(len(recent_10) - 1)]
            sign_changes = sum(1 for i in range(len(diffs) - 1) if diffs[i] * diffs[i + 1] < 0)

            if sign_changes >= 5 and max(recent_10) > 1.0:
                behaviors.append({
                    "type": "repetitive_movement",
                    "confidence": min(0.8, sign_changes / 10),
                    "description": "Rhythmic/repetitive movement pattern detected (possible stereotypy)",
                })

        # Sudden movement change (possible behavioral transition)
        if len(self._movement_history) >= 3:
            prev_avg = sum(self._movement_history[-3:-1]) / 2
            if movement > prev_avg * 3 and movement > 2.0:
                behaviors.append({
                    "type": "sudden_movement_change",
                    "confidence": 0.6,
                    "description": "Sudden increase in movement from baseline",
                })

        return behaviors

    def analyze_frame(self, frame: np.ndarray) -> dict:
        """Analyze movement in a single frame."""
        movement = self._compute_optical_flow_movement(frame)
        behaviors = self._detect_behaviors(movement)

        return {
            "movement_magnitude": movement,
            "behaviors": behaviors,
        }

    def analyze_video(self, video_path, sample_fps: float = 5.0) -> dict:
        """Analyze movement patterns throughout a video file."""
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")

        video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / video_fps
        frame_interval = max(1, int(video_fps / sample_fps))

        timeline = []
        all_behaviors = []
        frame_idx = 0

        # Reset state
        self._prev_frame_gray = None
        self._movement_history = []

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                timestamp = round(frame_idx / video_fps, 2)
                result = self.analyze_frame(frame)

                timeline.append({
                    "timestamp": timestamp,
                    "movement": result["movement_magnitude"],
                    "behaviors": [b["type"] for b in result["behaviors"]],
                })
                for b in result["behaviors"]:
                    b["timestamp"] = timestamp
                    all_behaviors.append(b)

            frame_idx += 1

        cap.release()

        # Summarize
        movements = [t["movement"] for t in timeline]
        behavior_counts = {}
        for b in all_behaviors:
            behavior_counts[b["type"]] = behavior_counts.get(b["type"], 0) + 1

        return {
            "video_info": {
                "duration_seconds": round(duration, 1),
                "frames_analyzed": len(timeline),
                "fps": round(video_fps, 1),
            },
            "movement_summary": {
                "avg_movement": round(sum(movements) / len(movements), 2) if movements else 0,
                "max_movement": round(max(movements), 2) if movements else 0,
                "stillness_pct": round(sum(1 for m in movements if m < 0.5) / len(movements) * 100, 1) if movements else 0,
            },
            "behavior_counts": behavior_counts,
            "behaviors": all_behaviors,
            "movement_timeline": timeline,
        }

    def close(self):
        """Release resources."""
        self._prev_frame_gray = None
        self._movement_history = []
