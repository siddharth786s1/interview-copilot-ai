"""
Speech-to-Text provider interface and shared data structures.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class TranscriptChunkResult:
    """Output from a SpeechToTextProvider for a chunk of audio."""
    text: str
    source: str  # "mic" | "tab"
    is_final: bool = True
    language: str = "en"
    confidence: float = 1.0
    timestamp: datetime = field(default_factory=_utcnow)
    latency_ms: int = 0


class SpeechToTextProvider(ABC):
    """Provider-independent interface for speech-to-text transcription."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider identifier."""
        ...

    @abstractmethod
    async def transcribe_pcm(
        self,
        audio_pcm: bytes,
        source: str,
        language: str = "en",
        is_final: bool = True,
    ) -> List[TranscriptChunkResult]:
        """
        Transcribe 16kHz, 16-bit signed little-endian mono PCM audio bytes.

        Args:
            audio_pcm: Raw linear16 mono PCM bytes at 16,000 Hz.
            source: Audio source identifier ("mic" or "tab").
            language: ISO-639-1 language code (e.g. "en", "es", "fr", or "auto").
            is_final: Whether this chunk represents a finalized utterance window.

        Returns:
            List of TranscriptChunkResult items (empty if silence/no speech).
        """
        ...

    async def close(self) -> None:
        """Release any underlying resources."""
        return None
