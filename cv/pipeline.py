"""CV processing pipeline — runs detection + tracking on video files or frame streams."""

import cv2
import time
from pathlib import Path

from cv.detector import PersonDetector
from cv.tracker import CentroidTracker
from cv.zones import ZoneManager


def _to_python(obj):
    """Convert numpy types to native Python types for JSON serialization."""
    import numpy as np
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: _to_python(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_python(i) for i in obj]
    return obj


class CVPipeline:
    """Process video for person detection, tracking, and zone analysis."""

    def __init__(
        self,
        confidence: float = 0.5,
        max_disappeared: int = 30,
        process_every_n: int = 3,
    ):
        """
        Args:
            confidence: Detection confidence threshold (0-1)
            max_disappeared: Frames before losing track of a person
            process_every_n: Run detection every N frames (skip for performance)
        """
        self._detector = PersonDetector(confidence_threshold=confidence)
        self._tracker = CentroidTracker(max_disappeared=max_disappeared)
        self._zones = ZoneManager()
        self._process_every_n = process_every_n

    @property
    def zones(self) -> ZoneManager:
        return self._zones

    def analyze_video(self, video_path: Path, sample_fps: float = 5.0) -> dict:
        """Analyze a video file and return CV metrics.

        Args:
            video_path: Path to video file
            sample_fps: How many frames per second to analyze (lower = faster)

        Returns:
            Dict with person counts, tracking data, zone events, and timeline
        """
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")

        video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / video_fps if video_fps > 0 else 0

        # Calculate frame skip interval
        frame_interval = max(1, int(video_fps / sample_fps))

        timeline = []       # Per-sample snapshot
        max_concurrent = 0
        frame_idx = 0
        self._tracker.reset()

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                timestamp = frame_idx / video_fps
                detections = self._detector.detect(frame)
                tracked = self._tracker.update(detections)

                current_count = len(tracked)
                max_concurrent = max(max_concurrent, current_count)

                # Check zones
                zone_occupancy = {}
                for track_id, info in tracked.items():
                    if info["centroid"]:
                        zones_in = self._zones.check_person(info["centroid"])
                        for z in zones_in:
                            zone_occupancy.setdefault(z, []).append(track_id)

                snapshot = {
                    "timestamp": round(timestamp, 2),
                    "frame": frame_idx,
                    "person_count": current_count,
                    "detections": len(detections),
                    "tracks": {
                        str(tid): {
                            "centroid": list(info["centroid"]),
                            "bbox": list(info["bbox"]) if info["bbox"] else None,
                        }
                        for tid, info in tracked.items()
                    },
                }
                if zone_occupancy:
                    snapshot["zone_occupancy"] = {
                        z: [str(tid) for tid in tids]
                        for z, tids in zone_occupancy.items()
                    }
                timeline.append(snapshot)

            frame_idx += 1

        cap.release()

        # Compute summary
        counts = [s["person_count"] for s in timeline]
        avg_count = sum(counts) / len(counts) if counts else 0

        return _to_python({
            "video_info": {
                "path": str(video_path.name),
                "duration_seconds": round(duration, 1),
                "total_frames": total_frames,
                "fps": round(video_fps, 1),
                "frames_analyzed": len(timeline),
            },
            "summary": {
                "total_unique_people": self._tracker.total_seen,
                "max_concurrent_people": max_concurrent,
                "avg_people_per_frame": round(avg_count, 1),
            },
            "zones_defined": self._zones.list_zones(),
            "timeline": timeline,
        })

    def process_frame(self, frame) -> dict:
        """Process a single frame (for live feeds). Returns current state."""
        detections = self._detector.detect(frame)
        tracked = self._tracker.update(detections)

        zone_occupancy = {}
        for track_id, info in tracked.items():
            if info["centroid"]:
                zones_in = self._zones.check_person(info["centroid"])
                for z in zones_in:
                    zone_occupancy.setdefault(z, []).append(track_id)

        return _to_python({
            "person_count": len(tracked),
            "detections": len(detections),
            "tracks": {
                str(tid): {
                    "centroid": list(info["centroid"]),
                    "bbox": list(info["bbox"]) if info["bbox"] else None,
                }
                for tid, info in tracked.items()
            },
            "zone_occupancy": {
                z: [str(tid) for tid in tids]
                for z, tids in zone_occupancy.items()
            } if zone_occupancy else {},
            "total_unique": self._tracker.total_seen,
        })
