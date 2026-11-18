"""
Factory for instantiating the configured SpeechToTextProvider.
"""
import logging
from typing import Optional

from app.core.config import settings
from app.services.transcription.base import SpeechToTextProvider
from app.services.transcription.whisper_provider import WhisperProvider
from app.services.transcription.deepgram_provider import DeepgramProvider

logger = logging.getLogger(__name__)

# Cached provider instance for local Whisper so model isn't reloaded per session
_cached_providers: dict[str, SpeechToTextProvider] = {}


def get_stt_provider(
    provider_name: Optional[str] = None,
    whisper_model_size: Optional[str] = None,
) -> SpeechToTextProvider:
    name = (provider_name or settings.stt_provider or "whisper").lower()

    if name == "deepgram":
        key = "deepgram"
        if key not in _cached_providers:
            _cached_providers[key] = DeepgramProvider()
        return _cached_providers[key]

    # Default: local faster-whisper
    model_size = whisper_model_size or settings.whisper_model_size or "base"
    key = f"whisper:{model_size}"
    if key not in _cached_providers:
        _cached_providers[key] = WhisperProvider(model_size=model_size)
    return _cached_providers[key]
