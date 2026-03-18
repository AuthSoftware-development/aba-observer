"""Tests for CV pipeline — detection, tracking, zones."""

import numpy as np
import pytest


def test_person_detector_loads():
    from cv.detector import PersonDetector
    detector = PersonDetector(confidence_threshold=0.5)
    assert detector is not None


def test_person_detector_returns_empty_for_blank_frame():
    from cv.detector import PersonDetector
    detector = PersonDetector(confidence_threshold=0.5)
    blank = np.zeros((300, 300, 3), dtype=np.uint8)
    detections = detector.detect(blank)
    assert isinstance(detections, list)


def test_centroid_tracker_registers_new_objects():
    from cv.tracker import CentroidTracker
    tracker = CentroidTracker(max_disappeared=5)
    detections = [
        {"centroid": (100, 100), "bbox": (50, 50, 150, 150), "confidence": 0.9},
        {"centroid": (300, 300), "bbox": (250, 250, 350, 350), "confidence": 0.8},
    ]
    tracked = tracker.update(detections)
    assert len(tracked) == 2
    assert tracker.active_count == 2
    assert tracker.total_seen == 2


def test_centroid_tracker_persists_ids():
    from cv.tracker import CentroidTracker
    tracker = CentroidTracker(max_disappeared=5)

    # Frame 1
    d1 = [{"centroid": (100, 100), "bbox": (50, 50, 150, 150), "confidence": 0.9}]
    t1 = tracker.update(d1)
    id1 = list(t1.keys())[0]

    # Frame 2 — same person moved slightly
    d2 = [{"centroid": (105, 105), "bbox": (55, 55, 155, 155), "confidence": 0.9}]
    t2 = tracker.update(d2)
    id2 = list(t2.keys())[0]

    assert id1 == id2  # Same person, same ID


def test_centroid_tracker_deregisters_after_disappearance():
    from cv.tracker import CentroidTracker
    tracker = CentroidTracker(max_disappeared=2)

    tracker.update([{"centroid": (100, 100), "bbox": (50, 50, 150, 150), "confidence": 0.9}])
    assert tracker.active_count == 1

    # Person disappears for 3 frames
    for _ in range(3):
        tracker.update([])

    assert tracker.active_count == 0
    assert tracker.total_seen == 1


def test_zone_containment():
    from cv.zones import Zone
    zone = Zone("test", [(0, 0), (100, 0), (100, 100), (0, 100)], "monitor")
    assert zone.contains_point(50, 50) is True
    assert zone.contains_point(150, 150) is False


def test_zone_manager_check_person():
    from cv.zones import Zone, ZoneManager
    mgr = ZoneManager()
    mgr.add_zone(Zone("zone_a", [(0, 0), (200, 0), (200, 200), (0, 200)]))
    mgr.add_zone(Zone("zone_b", [(300, 300), (500, 300), (500, 500), (300, 500)]))

    assert "zone_a" in mgr.check_person((100, 100))
    assert "zone_b" not in mgr.check_person((100, 100))
    assert "zone_b" in mgr.check_person((400, 400))


def test_cv_pipeline_on_blank_video(test_dir):
    """Pipeline should handle a video with no people gracefully."""
    import cv2
    # Create a short blank video
    path = test_dir / "blank.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (320, 240))
    for _ in range(30):
        writer.write(np.zeros((240, 320, 3), dtype=np.uint8))
    writer.release()

    from cv.pipeline import CVPipeline
    pipeline = CVPipeline(confidence=0.5)
    results = pipeline.analyze_video(path, sample_fps=5.0)
    assert results["summary"]["total_unique_people"] == 0
    assert results["summary"]["max_concurrent_people"] == 0
    assert len(results["timeline"]) > 0
