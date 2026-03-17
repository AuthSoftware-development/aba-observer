"""Vehicle detection and counting using MobileNet-SSD.

Uses the same MobileNet-SSD model as person detection — it also detects
cars, buses, motorbikes, and bicycles.
"""

import cv2
import numpy as np
from pathlib import Path

from cv.detector import PROTOTXT, CAFFEMODEL, CLASSES


# Vehicle class IDs in MobileNet-SSD
VEHICLE_CLASSES = {
    "bicycle": CLASSES.index("bicycle"),
    "bus": CLASSES.index("bus"),
    "car": CLASSES.index("car"),
    "motorbike": CLASSES.index("motorbike"),
}


class VehicleDetector:
    """Detect vehicles in video frames using MobileNet-SSD (CPU-only)."""

    def __init__(self, confidence_threshold: float = 0.4):
        self._net = cv2.dnn.readNetFromCaffe(str(PROTOTXT), str(CAFFEMODEL))
        self._net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self._net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        self._confidence = confidence_threshold

    def detect(self, frame: np.ndarray) -> list[dict]:
        """Detect vehicles in a frame.

        Returns list of {"bbox": (x1,y1,x2,y2), "confidence": float,
                         "vehicle_type": str, "centroid": (cx,cy)}
        """
        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(
            cv2.resize(frame, (300, 300)), 0.007843, (300, 300), 127.5
        )
        self._net.setInput(blob)
        raw = self._net.forward()

        detections = []
        for i in range(raw.shape[2]):
            confidence = float(raw[0, 0, i, 2])
            class_id = int(raw[0, 0, i, 1])

            # Check if it's a vehicle class
            vehicle_type = None
            for vtype, vid in VEHICLE_CLASSES.items():
                if class_id == vid and confidence >= self._confidence:
                    vehicle_type = vtype
                    break

            if not vehicle_type:
                continue

            x1 = max(0, int(raw[0, 0, i, 3] * w))
            y1 = max(0, int(raw[0, 0, i, 4] * h))
            x2 = min(w, int(raw[0, 0, i, 5] * w))
            y2 = min(h, int(raw[0, 0, i, 6] * h))

            detections.append({
                "bbox": (x1, y1, x2, y2),
                "confidence": round(confidence, 3),
                "vehicle_type": vehicle_type,
                "centroid": ((x1 + x2) // 2, (y1 + y2) // 2),
            })

        return detections

    def analyze_video(self, video_path, sample_fps: float = 1.0) -> dict:
        """Count and track vehicles in a video."""
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")

        video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / video_fps
        frame_interval = max(1, int(video_fps / sample_fps))

        timeline = []
        type_counts = {vtype: 0 for vtype in VEHICLE_CLASSES}
        max_concurrent = 0
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                timestamp = round(frame_idx / video_fps, 2)
                detections = self.detect(frame)
                count = len(detections)
                max_concurrent = max(max_concurrent, count)

                for d in detections:
                    type_counts[d["vehicle_type"]] = type_counts.get(d["vehicle_type"], 0) + 1

                timeline.append({
                    "timestamp": timestamp,
                    "vehicle_count": count,
                    "types": [d["vehicle_type"] for d in detections],
                })

            frame_idx += 1

        cap.release()

        return {
            "video_info": {
                "duration_seconds": round(duration, 1),
                "frames_analyzed": len(timeline),
            },
            "summary": {
                "max_concurrent_vehicles": max_concurrent,
                "type_counts": {k: v for k, v in type_counts.items() if v > 0},
            },
            "timeline": timeline,
        }
