"""Centroid-based multi-object tracker for person tracking across frames."""

from collections import OrderedDict
import numpy as np
from scipy.spatial import distance as dist


class CentroidTracker:
    """Track people across frames using centroid distance matching.

    Assigns persistent IDs to detected people and tracks them as they move.
    Simpler and faster than DeepSORT — suitable for CPU-only environments.
    """

    def __init__(self, max_disappeared: int = 30):
        """
        Args:
            max_disappeared: Number of consecutive frames a person can be
                missing before their ID is deregistered.
        """
        self._next_id = 0
        self._objects: OrderedDict[int, np.ndarray] = OrderedDict()
        self._disappeared: OrderedDict[int, int] = OrderedDict()
        self._max_disappeared = max_disappeared

    def _register(self, centroid: np.ndarray) -> int:
        """Register a new tracked object."""
        obj_id = self._next_id
        self._objects[obj_id] = centroid
        self._disappeared[obj_id] = 0
        self._next_id += 1
        return obj_id

    def _deregister(self, obj_id: int):
        """Remove a tracked object."""
        del self._objects[obj_id]
        del self._disappeared[obj_id]

    def update(self, detections: list[dict]) -> dict[int, dict]:
        """Update tracker with new frame detections.

        Args:
            detections: List of detections from PersonDetector.detect()

        Returns:
            Dict mapping track_id → {"centroid": (cx, cy), "bbox": (x1, y1, x2, y2)}
        """
        # No detections: mark all existing objects as disappeared
        if len(detections) == 0:
            for obj_id in list(self._disappeared.keys()):
                self._disappeared[obj_id] += 1
                if self._disappeared[obj_id] > self._max_disappeared:
                    self._deregister(obj_id)
            return {
                oid: {"centroid": tuple(c.astype(int)), "bbox": None}
                for oid, c in self._objects.items()
            }

        input_centroids = np.array([d["centroid"] for d in detections])
        input_bboxes = [d["bbox"] for d in detections]

        # No existing objects: register all
        if len(self._objects) == 0:
            id_bbox_map = {}
            for i in range(len(input_centroids)):
                obj_id = self._register(input_centroids[i])
                id_bbox_map[obj_id] = {
                    "centroid": tuple(input_centroids[i]),
                    "bbox": input_bboxes[i],
                }
            return id_bbox_map

        # Match existing objects to new detections via centroid distance
        object_ids = list(self._objects.keys())
        object_centroids = list(self._objects.values())

        D = dist.cdist(np.array(object_centroids), input_centroids)
        rows = D.min(axis=1).argsort()
        cols = D.argmin(axis=1)[rows]

        used_rows = set()
        used_cols = set()
        matched = {}

        for row, col in zip(rows, cols):
            if row in used_rows or col in used_cols:
                continue
            # Skip if distance is too large (likely different person)
            if D[row, col] > 200:
                continue

            obj_id = object_ids[row]
            self._objects[obj_id] = input_centroids[col]
            self._disappeared[obj_id] = 0
            matched[obj_id] = {
                "centroid": tuple(input_centroids[col]),
                "bbox": input_bboxes[col],
            }
            used_rows.add(row)
            used_cols.add(col)

        # Handle unmatched existing objects (disappeared)
        for row in range(len(object_centroids)):
            if row not in used_rows:
                obj_id = object_ids[row]
                self._disappeared[obj_id] += 1
                if self._disappeared[obj_id] > self._max_disappeared:
                    self._deregister(obj_id)

        # Handle unmatched new detections (new people)
        for col in range(len(input_centroids)):
            if col not in used_cols:
                obj_id = self._register(input_centroids[col])
                matched[obj_id] = {
                    "centroid": tuple(input_centroids[col]),
                    "bbox": input_bboxes[col],
                }

        return matched

    @property
    def active_count(self) -> int:
        """Number of currently tracked people."""
        return len(self._objects)

    @property
    def total_seen(self) -> int:
        """Total unique people seen since tracker was created."""
        return self._next_id

    def reset(self):
        """Reset tracker state."""
        self._next_id = 0
        self._objects.clear()
        self._disappeared.clear()
