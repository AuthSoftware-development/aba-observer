"""Abstract base for AI providers."""

from abc import ABC, abstractmethod
from pathlib import Path


class ObservationProvider(ABC):
    """Base class for multimodal observation providers."""

    name: str = "base"

    @abstractmethod
    def analyze_video(self, video_path: Path, system_prompt: str) -> dict:
        """Analyze a video file and return structured ABA observation data.

        Args:
            video_path: Path to the video file.
            system_prompt: The ABA observation system prompt.

        Returns:
            Parsed JSON dict with observation data.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is ready to use."""
        ...
