"""
Phase 10 Desktop Companion Integration Tests:
- Verifies float32 -> 16kHz 16-bit mono PCM + source header framing
- Verifies Windows WASAPI loopback endpoint discovery on Windows
- Streams companion-encoded frames directly into the existing FastAPI /ws/audio/{session_id}
  endpoint and verifies end-to-end transcript + question + streaming answer delivery with
  ZERO changes to existing backend services.
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import AsyncIterator

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel

# Allow importing desktop_companion from repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from desktop_companion.wasapi_bridge import (  # noqa: E402
    SOURCE_LOOPBACK_BYTE,
    SOURCE_MIC_BYTE,
    compute_rms_level,
    float32_to_pcm16_frame,
    list_wasapi_devices,
)
from app.api.websockets.manager import ws_manager  # noqa: E402
from app.database.connection import get_session  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.services.answer_generation.base import LLMProvider  # noqa: E402
from app.services.transcription.base import SpeechToTextProvider, TranscriptChunkResult  # noqa: E402
import app.models  # noqa: F401, E402


class CompanionTestSTT(SpeechToTextProvider):
    @property
    def name(self) -> str:
        return "companion-test-stt"

    async def transcribe_pcm(self, audio_pcm: bytes, source: str, language: str = "en", is_final: bool = True):
        return [
            TranscriptChunkResult(
                text="Explain the difference between authentication and authorization.",
                source=source,
                is_final=is_final,
                language=language,
                latency_ms=8,
            )
        ]


class CompanionTestLLM(LLMProvider):
    @property
    def name(self) -> str:
        return "companion-test-llm"

    @property
    def model_name(self) -> str:
        return "mock-flash"

    async def stream_generate(
        self, system_prompt: str, user_prompt: str, max_tokens: int = 800, temperature: float = 0.3
    ) -> AsyncIterator[str]:
        yield "Authentication verifies identity; "
        yield "authorization verifies permissions."


def test_wasapi_frame_encoding_and_stereo_downmix():
    # Stereo float32 clip (0.5s at 16kHz = 8000 frames)
    t = np.linspace(0, 0.5, 8000, endpoint=False, dtype=np.float32)
    sine = 0.5 * np.sin(2 * np.pi * 440.0 * t)
    stereo = np.column_stack([sine, sine])

    frame = float32_to_pcm16_frame(stereo, SOURCE_LOOPBACK_BYTE)
    assert frame[0] == 0x02
    assert len(frame) == 1 + 8000 * 2  # header + 16-bit mono samples
    assert compute_rms_level(sine) > 0.5

    mic_frame = float32_to_pcm16_frame(sine, SOURCE_MIC_BYTE)
    assert mic_frame[0] == 0x01


@pytest.mark.skipif(sys.platform != "win32", reason="Windows WASAPI loopback test runs on Windows")
def test_windows_wasapi_loopback_device_enumeration():
    devices = list_wasapi_devices()
    assert len(devices) >= 1
    assert any(d.is_loopback for d in devices), "Expected at least one Windows WASAPI loopback endpoint"


def test_companion_frames_flow_through_existing_backend_without_rewrite(tmp_path):
    db_file = tmp_path / "companion_test.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_file.as_posix()}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _init():
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        await engine.dispose()

    asyncio.run(_init())

    async def override_get_session():
        async with session_factory() as db:
            yield db

    orig_stt = ws_manager.stt_provider_factory
    orig_llm = ws_manager.llm_provider_factory
    orig_db = ws_manager.db_session_factory
    orig_auto = ws_manager.auto_generate_answers

    ws_manager.stt_provider_factory = lambda: CompanionTestSTT()
    ws_manager.llm_provider_factory = lambda _p=None, _m=None: CompanionTestLLM()
    ws_manager.db_session_factory = session_factory
    ws_manager.auto_generate_answers = True
    fastapi_app.dependency_overrides[get_session] = override_get_session

    try:
        with TestClient(fastapi_app) as client:
            s_id = client.post(
                "/api/sessions/", json={"title": "Zoom Desktop WASAPI PoC", "type": "technical"}
            ).json()["id"]

            t = np.linspace(0, 0.7, int(16000 * 0.7), endpoint=False, dtype=np.float32)
            speech_frame = float32_to_pcm16_frame(0.5 * np.sin(2 * np.pi * 440.0 * t), SOURCE_LOOPBACK_BYTE)
            silence_frame = float32_to_pcm16_frame(np.zeros(int(16000 * 0.7), dtype=np.float32), SOURCE_LOOPBACK_BYTE)

            with client.websocket_connect(f"/ws/session/{s_id}") as s_ws:
                _ = json.loads(s_ws.receive_text())
                with client.websocket_connect(f"/ws/audio/{s_id}") as a_ws:
                    a_ws.send_bytes(speech_frame)
                    a_ws.send_bytes(silence_frame)

                    events = []
                    for _ in range(10):
                        ev = json.loads(s_ws.receive_text())
                        events.append(ev)
                        if ev["type"] == "answer_complete":
                            break

            types = [e["type"] for e in events]
            assert "transcript" in types
            assert "question" in types
            assert "answer_complete" in types

            t_ev = next(e for e in events if e["type"] == "transcript")
            assert t_ev["source"] == "tab"
            assert t_ev["speaker_label"] == "Interviewer"

            ans_ev = next(e for e in events if e["type"] == "answer_complete")
            assert "Authentication verifies identity" in ans_ev["full_text"]
    finally:
        ws_manager.stt_provider_factory = orig_stt
        ws_manager.llm_provider_factory = orig_llm
        ws_manager.db_session_factory = orig_db
        ws_manager.auto_generate_answers = orig_auto
        ws_manager._transcript_managers.clear()
        ws_manager._question_engines.clear()
        ws_manager._session_sockets.clear()
        ws_manager._audio_sources.clear()
        ws_manager._answer_tasks.clear()
        fastapi_app.dependency_overrides.clear()
