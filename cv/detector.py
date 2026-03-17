"""Person detection using MobileNet-SSD via OpenCV DNN."""

import cv2
import numpy as np
from pathlib import Path

MODELS_DIR = Path(__file__).parent / "models"
PROTOTXT = MODELS_DIR / "MobileNetSSD_deploy.prototxt"
CAFFEMODEL = MODELS_DIR / "MobileNetSSD_deploy.caffemodel"

# MobileNet-SSD class labels
CLASSES = [
    "background", "aeroplane", "bicycle", "bird", "boat", "bottle",
    "bus", "car", "cat", "chair", "cow", "diningtable", "dog",
    "horse", "motorbike", "person", "pottedplant", "sheep", "sofa",
    "train", "tvmonitor",
]
PERSON_CLASS_ID = CLASSES.index("person")


class PersonDetector:
    """Detect people in video frames using MobileNet-SSD (CPU-only)."""

    def __init__(self, confidence_threshold: float = 0.5):
        if not PROTOTXT.exists() or not CAFFEMODEL.exists():
            raise FileNotFoundError(
                f"Model files not found in {MODELS_DIR}. "
                "Download MobileNetSSD_deploy.prototxt and .caffemodel."
            )
        self._net = cv2.dnn.readNetFromCaffe(str(PROTOTXT), str(CAFFEMODEL))
        self._net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self._net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        self._confidence_threshold = confidence_threshold

    def detect(self, frame: np.ndarray) -> list[dict]:
        """Detect people in a frame. Returns list of detections.

        Each detection: {"bbox": (x1, y1, x2, y2), "confidence": float, "centroid": (cx, cy)}
        """
        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(
            cv2.resize(frame, (300, 300)), 0.007843, (300, 300), 127.5
        )
        self._net.setInput(blob)
        raw_detections = self._net.forward()

        detections = []
        for i in range(raw_detections.shape[2]):
            confidence = float(raw_detections[0, 0, i, 2])
            class_id = int(raw_detections[0, 0, i, 1])

            if class_id != PERSON_CLASS_ID or confidence < self._confidence_threshold:
                continue

            x1 = max(0, int(raw_detections[0, 0, i, 3] * w))
            y1 = max(0, int(raw_detections[0, 0, i, 4] * h))
            x2 = min(w, int(raw_detections[0, 0, i, 5] * w))
            y2 = min(h, int(raw_detections[0, 0, i, 6] * h))
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2

            detections.append({
                "bbox": (x1, y1, x2, y2),
                "confidence": round(confidence, 3),
                "centroid": (cx, cy),
            })

        return detections
