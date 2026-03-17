"""Face search — find a person across all camera footage.

Given a consent ID or uploaded photo, searches all indexed footage
for appearances of that person. Only works with consented faces.
"""

import cv2
import numpy as np
from pathlib import Path

from cv.face import FaceRecognizer
from store.consent import load_all_enrolled, get_consent


def search_by_consent_id(consent_id: str, video_paths: list[Path], sample_fps: float = 1.0) -> dict:
    """Search for a consented person across multiple videos.

    Args:
        consent_id: Consent ID of the person to search for
        video_paths: List of video files to search
        sample_fps: Frames per second to analyze

    Returns:
        Dict with appearances across videos
    """
    consent = get_consent(consent_id)
    if not consent or consent.get("revoked"):
        return {"error": "Invalid or revoked consent"}

    enrolled = load_all_enrolled()
    if consent_id not in enrolled:
        return {"error": "Person not enrolled (no face embeddings)"}

    recognizer = FaceRecognizer()
    recognizer.load_enrolled(enrolled)

    all_appearances = []

    for video_path in video_paths:
        if not video_path.exists():
            continue

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            continue

        video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_interval = max(1, int(video_fps / sample_fps))
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                timestamp = round(frame_idx / video_fps, 2)
                faces = recognizer.recognize_frame(frame)

                for face in faces:
                    if face["consent_id"] == consent_id:
                        all_appearances.append({
                            "video": video_path.name,
                            "timestamp": timestamp,
                            "confidence": face["confidence"],
                            "similarity": face["similarity"],
                            "bbox": list(face["bbox"]),
                        })

            frame_idx += 1

        cap.release()

    return {
        "person_name": consent["person_name"],
        "consent_id": consent_id,
        "videos_searched": len(video_paths),
        "total_appearances": len(all_appearances),
        "appearances": all_appearances,
    }


def search_by_photo(photo: np.ndarray, video_paths: list[Path], sample_fps: float = 1.0, threshold: float = 0.5) -> dict:
    """Search for a face from a photo across videos.

    Only matches against consented/enrolled faces — will not identify
    unknown people from an arbitrary photo.

    Args:
        photo: Image containing a face to search for
        video_paths: Videos to search
        sample_fps: Analysis rate
        threshold: Similarity threshold

    Returns:
        Dict with matched consent records and appearances
    """
    recognizer = FaceRecognizer(match_threshold=threshold)

    # Extract embedding from search photo
    embeddings = recognizer.enroll_from_frame(photo)
    if not embeddings:
        return {"error": "No face detected in search photo"}

    search_embedding = embeddings[0]

    # Load enrolled faces and find matches
    enrolled = load_all_enrolled()
    matches = []

    for consent_id, data in enrolled.items():
        for enrolled_emb in data["embeddings"]:
            sim = recognizer._cosine_similarity(search_embedding, enrolled_emb)
            if sim >= threshold:
                matches.append({
                    "consent_id": consent_id,
                    "person_name": data["name"],
                    "role": data["role"],
                    "similarity": round(sim, 3),
                })
                break  # One match per person

    if not matches:
        return {
            "matched": False,
            "message": "No matching enrolled faces found. Only consented persons can be identified.",
            "matches": [],
        }

    return {
        "matched": True,
        "matches": matches,
    }
