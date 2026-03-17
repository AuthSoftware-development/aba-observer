"""Face detection and recognition using OpenCV DNN.

Uses res10_300x300 SSD for face detection and OpenFace nn4.small2.v1 for
128-d face embeddings. All CPU-only, no GPU required.

Face recognition is consent-based:
- Only identifies people who have been enrolled with explicit consent
- Unknown faces are labeled "Person A", "Person B", etc.
- No face data is ever stored without a consent record
"""

import cv2
import numpy as np
from pathlib import Path

MODELS_DIR = Path(__file__).parent / "models"
FACE_PROTO = MODELS_DIR / "face_detector.prototxt"
FACE_MODEL = MODELS_DIR / "face_detector.caffemodel"
EMBED_MODEL = MODELS_DIR / "openface.nn4.small2.v1.t7"


class FaceDetector:
    """Detect faces in frames using OpenCV DNN (res10 SSD)."""

    def __init__(self, confidence_threshold: float = 0.5):
        if not FACE_PROTO.exists() or not FACE_MODEL.exists():
            raise FileNotFoundError(
                f"Face detection model not found in {MODELS_DIR}. "
                "Run: python -m cv.models.download"
            )
        self._net = cv2.dnn.readNetFromCaffe(str(FACE_PROTO), str(FACE_MODEL))
        self._net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self._net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        self._confidence = confidence_threshold

    def detect(self, frame: np.ndarray) -> list[dict]:
        """Detect faces in a frame.

        Returns list of {"bbox": (x1,y1,x2,y2), "confidence": float}
        """
        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(
            cv2.resize(frame, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0)
        )
        self._net.setInput(blob)
        detections = self._net.forward()

        faces = []
        for i in range(detections.shape[2]):
            confidence = float(detections[0, 0, i, 2])
            if confidence < self._confidence:
                continue
            x1 = max(0, int(detections[0, 0, i, 3] * w))
            y1 = max(0, int(detections[0, 0, i, 4] * h))
            x2 = min(w, int(detections[0, 0, i, 5] * w))
            y2 = min(h, int(detections[0, 0, i, 6] * h))

            # Skip tiny detections
            if (x2 - x1) < 20 or (y2 - y1) < 20:
                continue

            faces.append({
                "bbox": (x1, y1, x2, y2),
                "confidence": round(confidence, 3),
            })
        return faces


class FaceEmbedder:
    """Generate 128-d face embeddings using OpenFace model."""

    def __init__(self):
        if not EMBED_MODEL.exists():
            raise FileNotFoundError(
                f"Face embedding model not found: {EMBED_MODEL}. "
                "Run: python -m cv.models.download"
            )
        self._net = cv2.dnn.readNetFromTorch(str(EMBED_MODEL))
        self._net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self._net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

    def embed(self, frame: np.ndarray, bbox: tuple[int, int, int, int]) -> list[float]:
        """Extract 128-d embedding from a face region.

        Args:
            frame: Full frame
            bbox: (x1, y1, x2, y2) face bounding box

        Returns:
            128-dimensional embedding vector (normalized)
        """
        x1, y1, x2, y2 = bbox
        face_roi = frame[y1:y2, x1:x2]
        if face_roi.size == 0:
            return []

        blob = cv2.dnn.blobFromImage(
            face_roi, 1.0 / 255, (96, 96), (0, 0, 0), swapRB=True, crop=False
        )
        self._net.setInput(blob)
        embedding = self._net.forward().flatten()

        # Normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding.tolist()


class FaceRecognizer:
    """Match detected faces against enrolled (consented) face embeddings.

    Unknown faces get anonymous labels ("Person A", "Person B").
    Only consented, enrolled faces are identified by name.
    """

    def __init__(self, match_threshold: float = 0.6):
        """
        Args:
            match_threshold: Cosine similarity threshold for a match (0-1).
                Higher = stricter matching. 0.6 is a good default.
        """
        self._detector = FaceDetector()
        self._embedder = FaceEmbedder()
        self._match_threshold = match_threshold
        self._enrolled: dict[str, dict] = {}  # consent_id → {name, role, domain, embeddings}
        self._anonymous_counter = 0
        self._anonymous_map: dict[str, str] = {}  # embedding_key → "Person A"

    def load_enrolled(self, enrolled: dict[str, dict]):
        """Load enrolled face data from consent store."""
        self._enrolled = enrolled

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two embeddings."""
        a_arr = np.array(a)
        b_arr = np.array(b)
        dot = np.dot(a_arr, b_arr)
        norm_a = np.linalg.norm(a_arr)
        norm_b = np.linalg.norm(b_arr)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))

    def _match_embedding(self, embedding: list[float]) -> dict | None:
        """Try to match an embedding against enrolled faces.

        Returns: {"consent_id": str, "name": str, "role": str, "similarity": float} or None
        """
        best_match = None
        best_sim = 0.0

        for consent_id, data in self._enrolled.items():
            for enrolled_emb in data["embeddings"]:
                sim = self._cosine_similarity(embedding, enrolled_emb)
                if sim > best_sim and sim >= self._match_threshold:
                    best_sim = sim
                    best_match = {
                        "consent_id": consent_id,
                        "name": data["name"],
                        "role": data["role"],
                        "domain": data["domain"],
                        "similarity": round(sim, 3),
                    }

        return best_match

    def _get_anonymous_label(self, embedding: list[float]) -> str:
        """Get or create an anonymous label for an unmatched face."""
        # Use a rough hash of the embedding to track seen faces
        key = str(round(sum(embedding[:10]), 4))
        if key not in self._anonymous_map:
            label_idx = self._anonymous_counter
            self._anonymous_counter += 1
            # A, B, C, ..., Z, AA, AB, ...
            label = ""
            while True:
                label = chr(65 + label_idx % 26) + label
                label_idx = label_idx // 26 - 1
                if label_idx < 0:
                    break
            self._anonymous_map[key] = f"Person {label}"
        return self._anonymous_map[key]

    def recognize_frame(self, frame: np.ndarray) -> list[dict]:
        """Detect and identify/anonymize all faces in a frame.

        Returns list of:
            {
                "bbox": (x1,y1,x2,y2),
                "confidence": float,
                "identified": bool,
                "name": str,           # Real name if consented, "Person X" otherwise
                "role": str | None,
                "consent_id": str | None,
                "similarity": float | None,
            }
        """
        faces = self._detector.detect(frame)
        results = []

        for face in faces:
            embedding = self._embedder.embed(frame, face["bbox"])
            if not embedding:
                continue

            match = self._match_embedding(embedding)
            if match:
                results.append({
                    "bbox": face["bbox"],
                    "confidence": face["confidence"],
                    "identified": True,
                    "name": match["name"],
                    "role": match["role"],
                    "consent_id": match["consent_id"],
                    "similarity": match["similarity"],
                })
            else:
                anon_label = self._get_anonymous_label(embedding)
                results.append({
                    "bbox": face["bbox"],
                    "confidence": face["confidence"],
                    "identified": False,
                    "name": anon_label,
                    "role": None,
                    "consent_id": None,
                    "similarity": None,
                })

        return results

    def enroll_from_frame(self, frame: np.ndarray) -> list[list[float]]:
        """Extract face embeddings from a frame for enrollment.

        Returns list of 128-d embeddings (one per detected face).
        Caller should verify only ONE face is present for clean enrollment.
        """
        faces = self._detector.detect(frame)
        embeddings = []
        for face in faces:
            emb = self._embedder.embed(frame, face["bbox"])
            if emb:
                embeddings.append(emb)
        return embeddings

    def enroll_from_images(self, images: list[np.ndarray]) -> list[list[float]]:
        """Extract embeddings from multiple enrollment images.

        Best practice: provide 3-5 images from different angles.
        Returns all extracted embeddings.
        """
        all_embeddings = []
        for img in images:
            embeddings = self.enroll_from_frame(img)
            all_embeddings.extend(embeddings)
        return all_embeddings

    def reset_anonymous(self):
        """Reset anonymous face labels (call between sessions)."""
        self._anonymous_counter = 0
        self._anonymous_map.clear()
