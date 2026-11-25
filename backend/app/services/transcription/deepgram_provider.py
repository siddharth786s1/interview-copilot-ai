"""
Cloud Speech-to-Text provider using Deepgram Nova-2 HTTP API for low-latency linear16 PCM.
"""
import logging
import time
from typing import List, Optional

import httpx

from app.core.config import settings
from app.core.exceptions import ProviderError
from app.services.transcription.base import SpeechToTextProvider, TranscriptChunkResult

logger = logging.getLogger(__name__)


class DeepgramProvider(SpeechToTextProvider):
    """Deepgram Nova-2 cloud transcription provider."""

    DEEPGRAM_URL = "https://api.deepgram.com/v1/listen"

    def __init__(self, api_key: Optional[str] = None, model: str = "nova-2"):
        self._api_key = api_key or settings.deepgram_api_key
        self._model = model
        self._client = httpx.AsyncClient(timeout=15.0)

    @property
    def name(self) -> str:
        return f"deepgram:{self._model}"

    async def transcribe_pcm(
        self,
        audio_pcm: bytes,
        source: str,
        language: str = "en",
        is_final: bool = True,
    ) -> List[TranscriptChunkResult]:
        if not self._api_key or self._api_key == "your-deepgram-api-key-here":
            raise ProviderError("deepgram", "DEEPGRAM_API_KEY is not configured in .env")

        if not audio_pcm or len(audio_pcm) < 3200:
            return []

        start_time = time.perf_counter()
        params = {
            "model": self._model,
            "encoding": "linear16",
            "sample_rate": "16000",
            "channels": "1",
            "punctuate": "true",
            "smart_format": "true",
        }
        if language and language not in ("auto", "bilingual_hi_en"):
            params["language"] = language
        else:
            params["detect_language"] = "true"

        headers = {
            "Authorization": f"Token {self._api_key}",
            "Content-Type": "audio/l16;rate=16000;channels=1",
        }

        try:
            resp = await self._client.post(
                self.DEEPGRAM_URL,
                params=params,
                headers=headers,
                content=audio_pcm,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as e:
            raise ProviderError("deepgram", f"Deepgram API request failed: {e}") from e

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        channels = data.get("results", {}).get("channels", [])
        if not channels:
            return []

        alternatives = channels[0].get("alternatives", [])
        if not alternatives:
            return []

        top = alternatives[0]
        transcript = top.get("transcript", "").strip()
        if not transcript:
            return []

        confidence = float(top.get("confidence", 0.9))
        detected_lang = channels[0].get("detected_language", language or "en")

        return [
            TranscriptChunkResult(
                text=transcript,
                source=source,
                is_final=is_final,
                language=detected_lang,
                confidence=round(confidence, 3),
                latency_ms=elapsed_ms,
            )
        ]

    async def close(self) -> None:
        await self._client.aclose()
