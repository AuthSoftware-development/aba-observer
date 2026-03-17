"""RTSP camera ingest — connect to IP cameras via RTSP/ONVIF streams."""

import cv2
import threading
import time
from dataclasses import dataclass, field


@dataclass
class CameraConfig:
    """Configuration for an RTSP camera."""
    camera_id: str
    name: str
    rtsp_url: str
    fps_target: float = 5.0        # Target FPS for processing (not capture)
    reconnect_delay: float = 5.0   # Seconds between reconnect attempts
    max_reconnects: int = 10       # Max consecutive reconnect attempts


class RTSPCamera:
    """Manages an RTSP camera connection with automatic reconnection.

    Captures frames in a background thread and provides the latest frame
    on demand — no frame queue buildup.
    """

    def __init__(self, config: CameraConfig):
        self.config = config
        self._cap: cv2.VideoCapture | None = None
        self._frame = None
        self._frame_lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._connected = False
        self._reconnect_count = 0
        self._last_frame_time = 0.0
        self._fps_actual = 0.0

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def latest_frame(self):
        """Get the most recent frame (thread-safe)."""
        with self._frame_lock:
            return self._frame.copy() if self._frame is not None else None

    @property
    def fps(self) -> float:
        return self._fps_actual

    def start(self):
        """Start capturing in background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop capturing."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        if self._cap:
            self._cap.release()
            self._cap = None
        self._connected = False

    def _connect(self) -> bool:
        """Attempt to connect to the RTSP stream."""
        if self._cap:
            self._cap.release()

        self._cap = cv2.VideoCapture(self.config.rtsp_url)
        # Set buffer size to 1 to minimize latency
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if self._cap.isOpened():
            self._connected = True
            self._reconnect_count = 0
            print(f"[rtsp] Connected to {self.config.name} ({self.config.rtsp_url})")
            return True

        self._connected = False
        return False

    def _capture_loop(self):
        """Background thread: continuously grab frames."""
        while self._running:
            if not self._connected:
                if self._reconnect_count >= self.config.max_reconnects:
                    print(f"[rtsp] {self.config.name}: Max reconnects reached, stopping")
                    self._running = False
                    break

                print(f"[rtsp] {self.config.name}: Connecting... (attempt {self._reconnect_count + 1})")
                if not self._connect():
                    self._reconnect_count += 1
                    time.sleep(self.config.reconnect_delay)
                    continue

            ret, frame = self._cap.read()
            if not ret:
                self._connected = False
                print(f"[rtsp] {self.config.name}: Lost connection")
                continue

            now = time.time()
            if self._last_frame_time > 0:
                dt = now - self._last_frame_time
                self._fps_actual = 1.0 / dt if dt > 0 else 0
            self._last_frame_time = now

            with self._frame_lock:
                self._frame = frame

            # Throttle to avoid burning CPU
            time.sleep(0.01)

    def get_snapshot(self) -> bytes | None:
        """Get current frame as JPEG bytes."""
        frame = self.latest_frame
        if frame is None:
            return None
        _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return jpeg.tobytes()

    def status(self) -> dict:
        return {
            "camera_id": self.config.camera_id,
            "name": self.config.name,
            "connected": self._connected,
            "fps": round(self._fps_actual, 1),
            "rtsp_url": self.config.rtsp_url,
        }


class CameraManager:
    """Manage multiple RTSP camera connections."""

    def __init__(self):
        self._cameras: dict[str, RTSPCamera] = {}

    def add_camera(self, config: CameraConfig) -> RTSPCamera:
        """Add and start a camera."""
        if config.camera_id in self._cameras:
            raise ValueError(f"Camera '{config.camera_id}' already exists")
        camera = RTSPCamera(config)
        self._cameras[config.camera_id] = camera
        camera.start()
        return camera

    def remove_camera(self, camera_id: str) -> bool:
        """Stop and remove a camera."""
        cam = self._cameras.pop(camera_id, None)
        if cam:
            cam.stop()
            return True
        return False

    def get_camera(self, camera_id: str) -> RTSPCamera | None:
        return self._cameras.get(camera_id)

    def list_cameras(self) -> list[dict]:
        return [cam.status() for cam in self._cameras.values()]

    def stop_all(self):
        """Stop all cameras."""
        for cam in self._cameras.values():
            cam.stop()
        self._cameras.clear()
