"""Google Gemini multimodal provider — video + audio analysis."""

import json
import os
import sys
import time
from pathlib import Path

from .base import ObservationProvider


class GeminiProvider(ObservationProvider):
    name = "gemini"

    def __init__(self, model: str = "gemini-2.5-flash"):
        self.model_name = model
        self._api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    def is_available(self) -> bool:
        if not self._api_key:
            print("[gemini] No API key found. Set GEMINI_API_KEY or GOOGLE_API_KEY env var.")
            return False
        try:
            from google import genai  # noqa: F401
            return True
        except ImportError:
            try:
                import google.generativeai  # noqa: F401
                print("[gemini] WARNING: Using deprecated google-generativeai. Run: pip install google-genai")
                return True
            except ImportError:
                print("[gemini] SDK not installed. Run: pip install google-genai")
                return False

    def analyze_video(self, video_path: Path, system_prompt: str) -> dict:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self._api_key)

        file_size_mb = video_path.stat().st_size / 1024 / 1024
        print(f"[gemini] Uploading video: {video_path.name} ({file_size_mb:.1f} MB)")
        video_file = client.files.upload(file=video_path)

        # Wait for processing
        print("[gemini] Processing video (this may take a minute)...")
        while video_file.state.name == "PROCESSING":
            time.sleep(5)
            video_file = client.files.get(name=video_file.name)
            sys.stdout.write(".")
            sys.stdout.flush()

        if video_file.state.name == "FAILED":
            raise RuntimeError(f"Gemini video processing failed: {video_file.state.name}")

        print(f"\n[gemini] Video ready. Analyzing with {self.model_name}...")

        response = client.models.generate_content(
            model=self.model_name,
            contents=[
                types.Content(
                    parts=[
                        types.Part.from_uri(file_uri=video_file.uri, mime_type=video_file.mime_type),
                        types.Part.from_text(text=system_prompt),
                    ]
                )
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )

        # Clean up uploaded file
        try:
            client.files.delete(name=video_file.name)
            print("[gemini] Cleaned up uploaded video file.")
        except Exception:
            pass

        raw = response.text
        return json.loads(raw)
