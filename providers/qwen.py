"""Qwen2.5-Omni local multimodal provider — video + audio analysis on-device."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from .base import ObservationProvider


class QwenProvider(ObservationProvider):
    name = "qwen"

    def __init__(self, model: str = "Qwen/Qwen2.5-Omni-7B"):
        self.model_id = model
        self._model = None
        self._processor = None

    def is_available(self) -> bool:
        try:
            import torch

            if not torch.cuda.is_available():
                print("[qwen] No CUDA GPU detected. Qwen2.5-Omni requires a GPU with 8GB+ VRAM.")
                print("[qwen] Tip: Use --provider gemini for cloud-based analysis instead.")
                return False

            vram = torch.cuda.get_device_properties(0).total_mem / (1024**3)
            if vram < 7:
                print(f"[qwen] GPU has {vram:.1f}GB VRAM. Qwen2.5-Omni 7B needs ~8GB+.")
                return False

            print(f"[qwen] GPU: {torch.cuda.get_device_name(0)} ({vram:.1f}GB VRAM)")
            return True
        except ImportError:
            print("[qwen] PyTorch not installed. Run: pip install torch")
            return False

    def _load_model(self):
        """Lazy-load the model on first use."""
        if self._model is not None:
            return

        print(f"[qwen] Loading {self.model_id} (first run downloads ~15GB)...")

        from transformers import AutoModelForCausalLM, AutoProcessor
        import torch

        self._processor = AutoProcessor.from_pretrained(self.model_id, trust_remote_code=True)
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True,
        )
        print("[qwen] Model loaded.")

    def _extract_audio(self, video_path: Path) -> Path:
        """Extract audio from video using ffmpeg."""
        audio_path = Path(tempfile.mktemp(suffix=".wav"))
        cmd = [
            "ffmpeg", "-i", str(video_path),
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            str(audio_path), "-y", "-loglevel", "quiet",
        ]
        subprocess.run(cmd, check=True)
        return audio_path

    def _sample_frames(self, video_path: Path, max_frames: int = 30) -> list:
        """Sample frames from video at even intervals."""
        import cv2
        import numpy as np

        cap = cv2.VideoCapture(str(video_path))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = total_frames / fps if fps > 0 else 0

        # Sample evenly across the video
        interval = max(1, total_frames // max_frames)
        frames = []
        timestamps = []

        for i in range(0, total_frames, interval):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()
            if ret:
                # Convert BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frames.append(frame_rgb)
                timestamps.append(i / fps if fps > 0 else 0)

            if len(frames) >= max_frames:
                break

        cap.release()
        print(f"[qwen] Sampled {len(frames)} frames from {duration:.1f}s video")
        return frames, timestamps

    def analyze_video(self, video_path: Path, system_prompt: str) -> dict:
        self._load_model()

        import torch
        import soundfile as sf

        # Extract audio
        print("[qwen] Extracting audio...")
        audio_path = self._extract_audio(video_path)
        audio_data, sr = sf.read(str(audio_path))

        # Sample frames
        print("[qwen] Sampling video frames...")
        frames, timestamps = self._sample_frames(video_path)

        # Build multimodal input
        # Qwen2.5-Omni uses a conversation format with mixed content
        messages = [
            {
                "role": "system",
                "content": [{"type": "text", "text": system_prompt}],
            },
            {
                "role": "user",
                "content": [
                    {"type": "video", "video": str(video_path)},
                    {"type": "audio", "audio": str(audio_path)},
                    {
                        "type": "text",
                        "text": "Analyze this ABA therapy session video and audio. Return structured JSON observation data.",
                    },
                ],
            },
        ]

        text = self._processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self._processor(
            text=text,
            videos=[str(video_path)],
            audios=[str(audio_path)],
            return_tensors="pt",
            padding=True,
        ).to(self._model.device)

        print("[qwen] Generating analysis (this may take a few minutes)...")
        with torch.no_grad():
            output_ids = self._model.generate(
                **inputs,
                max_new_tokens=4096,
                temperature=0.2,
                do_sample=True,
            )

        # Decode only the new tokens
        input_len = inputs["input_ids"].shape[1]
        raw = self._processor.decode(output_ids[0][input_len:], skip_special_tokens=True)

        # Clean up temp audio
        audio_path.unlink(missing_ok=True)

        # Parse JSON from response
        try:
            # Try to find JSON block in response
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0]
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0]
            return json.loads(raw.strip())
        except json.JSONDecodeError:
            print("[qwen] Warning: Could not parse structured JSON. Returning raw response.")
            return {"raw_response": raw, "parse_error": True}
