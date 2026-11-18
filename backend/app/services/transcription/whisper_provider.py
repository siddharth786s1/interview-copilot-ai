"""
Local Speech-to-Text provider using faster-whisper (CTranslate2).
Accepts 16kHz 16-bit mono PCM directly via numpy — no ffmpeg required.
"""
import asyncio
import logging
import os
import threading
import time
from pathlib import Path
from typing import List, Optional

import numpy as np

from app.core.config import settings
from app.core.exceptions import ProviderError
from app.services.transcription.base import SpeechToTextProvider, TranscriptChunkResult

logger = logging.getLogger(__name__)

# Common Whisper hallucinations on near-silent chunks
_HALLUCINATION_PHRASES = {
    "thank you",
    "thank you.",
    "thanks for watching",
    "thanks for watching.",
    "thanks for watching!",
    "you",
    "bye",
    "bye.",
    "subtitles by",
    "amara.org",
    "mbc",
}


class WhisperProvider(SpeechToTextProvider):
    """Local faster-whisper transcription provider."""

    def __init__(
        self,
        model_size: Optional[str] = None,
        device: str = "cpu",
        compute_type: str = "int8",
        download_root: Optional[str] = None,
    ):
        self._model_size = model_size or settings.whisper_model_size
        self._device = device
        self._compute_type = compute_type
        self._download_root = download_root or str(Path(settings.storage_path) / "models")
        self._model = None
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return f"whisper:{self._model_size}"

    def _get_model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    try:
                        from faster_whisper import WhisperModel

                        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
                        os.makedirs(self._download_root, exist_ok=True)
                        logger.info(
                            "Loading faster-whisper model '%s' (device=%s, compute=%s)...",
                            self._model_size,
                            self._device,
                            self._compute_type,
                        )
                        self._model = WhisperModel(
                            self._model_size,
                            device=self._device,
                            compute_type=self._compute_type,
                            download_root=self._download_root,
                        )
                        logger.info("faster-whisper model '%s' loaded.", self._model_size)
                    except Exception as e:
                        raise ProviderError("whisper", f"Failed to load model '{self._model_size}': {e}") from e
        return self._model

    def _transcribe_sync(
        self,
        audio_pcm: bytes,
        source: str,
        language: str,
        is_final: bool,
    ) -> List[TranscriptChunkResult]:
        if not audio_pcm or len(audio_pcm) < 3200:  # < 100ms at 16kHz 16-bit
            return []

        start_time = time.perf_counter()

        # Ensure even byte count for int16
        usable_len = len(audio_pcm) - (len(audio_pcm) % 2)
        audio_np = np.frombuffer(audio_pcm[:usable_len], dtype=np.int16).astype(np.float32) / 32768.0

        model = self._get_model()
        lang_arg = None if (not language or language == "auto") else language

        segments, info = model.transcribe(
            audio_np,
            language=lang_arg,
            beam_size=1 if not is_final else 3,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300},
            condition_on_previous_text=False,
        )

        texts = []
        probs = []
        for seg in segments:
            if getattr(seg, "no_speech_prob", 0.0) > 0.65:
                continue
            cleaned = seg.text.strip()
            if not cleaned:
                continue
            if cleaned.lower().strip(".!? ") in _HALLUCINATION_PHRASES:
                continue
            texts.append(cleaned)
            # Convert avg_logprob (~ -1.0 to 0.0) to approximate 0..1 confidence
            logprob = getattr(seg, "avg_logprob", -0.2)
            probs.append(max(0.0, min(1.0, float(np.exp(logprob)))))

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        full_text = " ".join(texts).strip()
        if not full_text:
            return []

        avg_conf = sum(probs) / len(probs) if probs else 0.85
        detected_lang = getattr(info, "language", language or "en")

        return [
            TranscriptChunkResult(
                text=full_text,
                source=source,
                is_final=is_final,
                language=detected_lang,
                confidence=round(avg_conf, 3),
                latency_ms=elapsed_ms,
            )
        ]

    async def transcribe_pcm(
        self,
        audio_pcm: bytes,
        source: str,
        language: str = "en",
        is_final: bool = True,
    ) -> List[TranscriptChunkResult]:
        return await asyncio.to_thread(
            self._transcribe_sync, audio_pcm, source, language, is_final
        )
