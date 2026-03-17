"""ROI zone management for defining areas of interest in camera frames."""

import cv2
import numpy as np
import json
from pathlib import Path


class Zone:
    """A named polygonal region of interest in a camera frame."""

    def __init__(self, name: str, points: list[tuple[int, int]], zone_type: str = "monitor"):
        """
        Args:
            name: Human-readable zone name (e.g., "therapy_table", "entrance")
            points: List of (x, y) polygon vertices
            zone_type: "monitor" (track presence), "entry" (count crossings),
                       "restricted" (alert on entry)
        """
        self.name = name
        self.points = points
        self.zone_type = zone_type
        self._polygon = np.array(points, dtype=np.int32)

    def contains_point(self, x: int, y: int) -> bool:
        """Check if a point (centroid) is inside this zone."""
        result = cv2.pointPolygonTest(self._polygon, (float(x), float(y)), False)
        return result >= 0

    def contains_centroid(self, centroid: tuple[int, int]) -> bool:
        """Check if a centroid tuple is inside this zone."""
        return self.contains_point(centroid[0], centroid[1])

    def draw(self, frame: np.ndarray, color: tuple = (0, 255, 0), alpha: float = 0.2) -> np.ndarray:
        """Draw this zone on a frame with semi-transparent fill."""
        overlay = frame.copy()
        cv2.fillPoly(overlay, [self._polygon], color)
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        cv2.polylines(frame, [self._polygon], True, color, 2)
        # Label
        cx = int(np.mean([p[0] for p in self.points]))
        cy = int(np.mean([p[1] for p in self.points]))
        cv2.putText(frame, self.name, (cx - 30, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        return frame

    def to_dict(self) -> dict:
        return {"name": self.name, "points": self.points, "zone_type": self.zone_type}

    @classmethod
    def from_dict(cls, data: dict) -> "Zone":
        return cls(
            name=data["name"],
            points=[tuple(p) for p in data["points"]],
            zone_type=data.get("zone_type", "monitor"),
        )


class ZoneManager:
    """Manage multiple zones for a camera."""

    def __init__(self):
        self._zones: dict[str, Zone] = {}

    def add_zone(self, zone: Zone):
        self._zones[zone.name] = zone

    def remove_zone(self, name: str) -> bool:
        if name in self._zones:
            del self._zones[name]
            return True
        return False

    def get_zone(self, name: str) -> Zone | None:
        return self._zones.get(name)

    def list_zones(self) -> list[dict]:
        return [z.to_dict() for z in self._zones.values()]

    def check_person(self, centroid: tuple[int, int]) -> list[str]:
        """Return names of all zones containing this centroid."""
        return [
            name for name, zone in self._zones.items()
            if zone.contains_centroid(centroid)
        ]

    def draw_all(self, frame: np.ndarray) -> np.ndarray:
        """Draw all zones on a frame."""
        colors = {
            "monitor": (0, 255, 0),     # green
            "entry": (255, 255, 0),     # yellow
            "restricted": (0, 0, 255),  # red
        }
        for zone in self._zones.values():
            color = colors.get(zone.zone_type, (0, 255, 0))
            zone.draw(frame, color=color)
        return frame

    def save(self, path: Path):
        """Save zones to JSON file."""
        data = [z.to_dict() for z in self._zones.values()]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load(self, path: Path):
        """Load zones from JSON file."""
        if not path.exists():
            return
        with open(path) as f:
            data = json.load(f)
        for item in data:
            self.add_zone(Zone.from_dict(item))
