"""E2E: CV pipeline — upload video → person detection → tracking results."""

import cv2
import numpy as np
from pathlib import Path


def test_cv_analyze_blank_video(client, auth_headers, test_dir):
    """Upload a blank video → CV returns 0 people detected."""
    # Create a short blank video
    video_path = test_dir / "blank_e2e.mp4"
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (320, 240))
    for _ in range(30):
        writer.write(np.zeros((240, 320, 3), dtype=np.uint8))
    writer.release()

    with open(video_path, "rb") as f:
        r = client.post("/api/cv/analyze",
                        files={"video": ("blank.mp4", f, "video/mp4")},
                        data={"confidence": "0.5", "sample_fps": "5.0"},
                        headers=auth_headers)

    assert r.status_code == 200
    data = r.json()
    assert data["summary"]["total_unique_people"] == 0
    assert data["summary"]["max_concurrent_people"] == 0
    assert len(data["timeline"]) > 0
    assert "video_info" in data


def test_cv_analyze_requires_auth(client, test_dir):
    """CV endpoint rejects unauthenticated requests."""
    video_path = test_dir / "noauth.mp4"
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (320, 240))
    for _ in range(10):
        writer.write(np.zeros((240, 320, 3), dtype=np.uint8))
    writer.release()

    with open(video_path, "rb") as f:
        r = client.post("/api/cv/analyze",
                        files={"video": ("test.mp4", f, "video/mp4")},
                        data={"confidence": "0.5", "sample_fps": "5.0"})

    assert r.status_code == 401


def test_camera_crud_lifecycle(client, auth_headers):
    """Add camera → list → remove → list empty."""
    # List (empty)
    r = client.get("/api/cameras", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []

    # Add
    r = client.post("/api/cameras",
                    json={"camera_id": "e2e-cam", "name": "E2E Test Camera", "rtsp_url": "rtsp://fake:554/stream"},
                    headers={**auth_headers, "Content-Type": "application/json"})
    assert r.status_code == 200
    assert r.json()["camera_id"] == "e2e-cam"

    # List (has 1)
    r = client.get("/api/cameras", headers=auth_headers)
    assert len(r.json()) == 1
    assert r.json()[0]["name"] == "E2E Test Camera"

    # Remove
    r = client.delete("/api/cameras/e2e-cam", headers=auth_headers)
    assert r.status_code == 200

    # List (empty again)
    r = client.get("/api/cameras", headers=auth_headers)
    assert r.json() == []
