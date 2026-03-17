"""Safety detection — slip/fall, unusual motion, loitering, crowd density.

Uses motion analysis and person tracking to detect safety-relevant events.
All CPU-only, no GPU required.
"""

import cv2
import numpy as np
import time
from collections import defaultdict


class SafetyDetector:
    """Detect safety events from video frames using motion analysis."""

    def __init__(self):
        self._prev_gray = None
        self._person_positions = defaultdict(list)  # track_id → [(timestamp, centroid, bbox)]
        self._alerts = []

    def analyze_with_tracks(self, frame: np.ndarray, tracks: dict, timestamp: float) -> list[dict]:
        """Analyze frame for safety events using person tracking data.

        Args:
            frame: Current video frame
            tracks: Dict from CentroidTracker {id: {"centroid": (x,y), "bbox": (x1,y1,x2,y2)}}
            timestamp: Current timestamp in seconds

        Returns:
            List of detected safety events
        """
        events = []
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Track positions over time
        for tid, info in tracks.items():
            tid_str = str(tid)
            if info.get("centroid") and info.get("bbox"):
                self._person_positions[tid_str].append({
                    "timestamp": timestamp,
                    "centroid": info["centroid"],
                    "bbox": info["bbox"],
                })
                # Keep last 60 entries per person
                if len(self._person_positions[tid_str]) > 60:
                    self._person_positions[tid_str].pop(0)

        # Check for falls
        for tid_str, positions in self._person_positions.items():
            fall = self._detect_fall(positions)
            if fall:
                events.append({
                    "type": "possible_fall",
                    "severity": "high",
                    "timestamp": timestamp,
                    "track_id": tid_str,
                    "confidence": fall["confidence"],
                    "description": fall["description"],
                })

        # Check for loitering
        for tid_str, positions in self._person_positions.items():
            loiter = self._detect_loitering(positions, threshold_seconds=60)
            if loiter:
                events.append({
                    "type": "loitering",
                    "severity": "low",
                    "timestamp": timestamp,
                    "track_id": tid_str,
                    "confidence": loiter["confidence"],
                    "description": loiter["description"],
                })

        # Crowd density check
        if len(tracks) >= 5:
            events.append({
                "type": "crowd_forming",
                "severity": "medium",
                "timestamp": timestamp,
                "track_id": None,
                "confidence": min(0.9, len(tracks) / 10),
                "description": f"Crowd of {len(tracks)} people detected",
            })

        # Running/rapid movement detection
        for tid_str, positions in self._person_positions.items():
            rapid = self._detect_rapid_movement(positions)
            if rapid:
                events.append({
                    "type": "rapid_movement",
                    "severity": "medium",
                    "timestamp": timestamp,
                    "track_id": tid_str,
                    "confidence": rapid["confidence"],
                    "description": rapid["description"],
                })

        self._prev_gray = gray
        return events

    def _detect_fall(self, positions: list[dict]) -> dict | None:
        """Detect possible fall by analyzing bounding box aspect ratio change.

        A fall typically shows: tall bbox → wide bbox (person goes from standing to horizontal).
        """
        if len(positions) < 3:
            return None

        recent = positions[-5:]  # Last 5 frames
        if len(recent) < 3:
            return None

        # Check aspect ratio change
        ratios = []
        for p in recent:
            bbox = p["bbox"]
            if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
                if w > 0 and h > 0:
                    ratios.append(h / w)  # >1 = tall (standing), <1 = wide (fallen)

        if len(ratios) < 3:
            return None

        # Detect transition from tall to wide
        first_ratio = sum(ratios[:2]) / 2
        last_ratio = ratios[-1]

        if first_ratio > 1.3 and last_ratio < 0.9:
            confidence = min(0.85, (first_ratio - last_ratio) / 2)
            return {
                "confidence": round(confidence, 2),
                "description": f"Aspect ratio changed from {first_ratio:.1f} to {last_ratio:.1f} (possible fall)",
            }

        # Also detect sudden vertical drop of centroid
        if len(positions) >= 3:
            y_values = [p["centroid"][1] for p in positions[-5:] if p.get("centroid")]
            if len(y_values) >= 3:
                y_drop = y_values[-1] - min(y_values[:-1])
                if y_drop > 100:  # Significant downward movement
                    return {
                        "confidence": min(0.7, y_drop / 200),
                        "description": f"Sudden vertical drop of {y_drop:.0f}px detected",
                    }

        return None

    def _detect_loitering(self, positions: list[dict], threshold_seconds: float = 60) -> dict | None:
        """Detect if a person has been in roughly the same area for too long."""
        if len(positions) < 5:
            return None

        first_ts = positions[0]["timestamp"]
        last_ts = positions[-1]["timestamp"]
        duration = last_ts - first_ts

        if duration < threshold_seconds:
            return None

        # Check if person stayed within a small radius
        centroids = [p["centroid"] for p in positions if p.get("centroid")]
        if len(centroids) < 3:
            return None

        xs = [c[0] for c in centroids]
        ys = [c[1] for c in centroids]
        spread_x = max(xs) - min(xs)
        spread_y = max(ys) - min(ys)
        spread = max(spread_x, spread_y)

        if spread < 150:  # Stayed within ~150px radius
            return {
                "confidence": min(0.8, duration / 120),
                "description": f"Person stationary for {duration:.0f}s in {spread:.0f}px radius",
            }

        return None

    def _detect_rapid_movement(self, positions: list[dict]) -> dict | None:
        """Detect someone running or moving very fast."""
        if len(positions) < 3:
            return None

        recent = positions[-3:]
        speeds = []

        for i in range(1, len(recent)):
            dt = recent[i]["timestamp"] - recent[i - 1]["timestamp"]
            if dt <= 0:
                continue
            c1 = recent[i - 1]["centroid"]
            c2 = recent[i]["centroid"]
            dist = np.sqrt((c2[0] - c1[0]) ** 2 + (c2[1] - c1[1]) ** 2)
            speed = dist / dt  # pixels per second
            speeds.append(speed)

        if not speeds:
            return None

        avg_speed = sum(speeds) / len(speeds)
        if avg_speed > 300:  # Very fast movement
            return {
                "confidence": min(0.8, avg_speed / 500),
                "description": f"Rapid movement at {avg_speed:.0f} px/s (possible running)",
            }

        return None

    def reset(self):
        """Reset detector state."""
        self._prev_gray = None
        self._person_positions.clear()
        self._alerts.clear()
