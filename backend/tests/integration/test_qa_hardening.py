"""
Phase 9 QA Hardening Tests:
- Failure injection: LLM HTTP 500, LLM timeout (504), transient recovery
- Malformed WebSocket frames (invalid JSON, empty bytes, 1-byte header, unknown control)
- Session persistence & recovery across disconnect/refresh
- Secret redaction in logs and zero secret leakage in API responses
- Boundary input validation & 404/422 enforcement across all modules
"""
import asyncio
import json
import logging
import math
import struct
from typing import AsyncIterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel

from app.api.websockets.manager import ws_manager
from app.core.logging import SecretRedactionFilter, redact_secrets
from app.database.connection import get_session
from app.main import app as fastapi_app
from app.services.answer_generation.base import LLMProvider, LLMProviderError
from app.services.transcription.base import SpeechToTextProvider, TranscriptChunkResult
import app.models  # noqa: F401


def _sine_pcm(duration_sec: float) -> bytes:
    n = int(16000 * duration_sec)
    samples = [int(0.5 * 32767 * math.sin(2 * math.pi * 440.0 * i / 16000)) for i in range(n)]
    return struct.pack(f"<{n}h", *samples)


def _silence_pcm(duration_sec: float) -> bytes:
    return b"\x00\x00" * int(16000 * duration_sec)


class FaultyLLM(LLMProvider):
    def __init__(self, mode: str):
        self.mode = mode

    @property
    def name(self) -> str:
        return "faulty-llm"

    @property
    def model_name(self) -> str:
        return "faulty-v1"

    async def stream_generate(
        self, system_prompt: str, user_prompt: str, max_tokens: int = 800, temperature: float = 0.3
    ) -> AsyncIterator[str]:
        if self.mode == "500":
            raise LLMProviderError(
                provider="faulty-llm",
                message="Upstream HTTP 500 Internal Server Error",
                code="LLM_PROVIDER_ERROR",
                retryable=False,
                status_code=500,
            )
        if self.mode == "timeout":
            raise LLMProviderError(
                provider="faulty-llm",
                message="Request timed out after 30s",
                code="LLM_TIMEOUT",
                retryable=False,
            )
        yield "Recovered healthy response."


class EchoSTT(SpeechToTextProvider):
    @property
    def name(self) -> str:
        return "echo-stt"

    async def transcribe_pcm(self, audio_pcm: bytes, source: str, language: str = "en", is_final: bool = True):
        return [TranscriptChunkResult(text="What is SQL injection?", source=source, is_final=is_final, latency_ms=5)]


@pytest.fixture
def qa_client(tmp_path):
    db_file = tmp_path / "qa_test.db"
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

    ws_manager.db_session_factory = session_factory
    ws_manager.auto_generate_answers = False
    fastapi_app.dependency_overrides[get_session] = override_get_session

    with TestClient(fastapi_app) as client:
        yield client

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


def test_failure_injection_llm_500_timeout_and_recovery(qa_client: TestClient):
    s_id = qa_client.post("/api/sessions/", json={"title": "Failure Injection", "type": "technical"}).json()["id"]
    q_id = qa_client.post(
        f"/api/sessions/{s_id}/questions",
        json={"question_text": "What is SQL injection?", "auto_generate": False},
    ).json()["id"]

    # 1. Inject upstream HTTP 500
    ws_manager.llm_provider_factory = lambda _p=None, _m=None: FaultyLLM("500")
    r500 = qa_client.post(f"/api/sessions/{s_id}/questions/{q_id}/answer", json={"style": "short"})
    assert r500.status_code == 500
    assert r500.json()["detail"]["code"] == "LLM_PROVIDER_ERROR"

    # 2. Inject timeout -> structured 504 LLM_TIMEOUT
    ws_manager.llm_provider_factory = lambda _p=None, _m=None: FaultyLLM("timeout")
    r504 = qa_client.post(f"/api/sessions/{s_id}/questions/{q_id}/answer", json={"style": "short"})
    assert r504.status_code == 504
    assert r504.json()["detail"]["code"] == "LLM_TIMEOUT"

    # 3. Recover cleanly on subsequent healthy call
    ws_manager.llm_provider_factory = lambda _p=None, _m=None: FaultyLLM("ok")
    r_ok = qa_client.post(f"/api/sessions/{s_id}/questions/{q_id}/answer", json={"style": "short"})
    assert r_ok.status_code == 201
    assert r_ok.json()["answer_text"] == "Recovered healthy response."


def test_malformed_websocket_frames_do_not_crash_pipeline(qa_client: TestClient):
    ws_manager.stt_provider_factory = lambda: EchoSTT()
    s_id = qa_client.post("/api/sessions/", json={"title": "Malformed WS Test", "type": "general"}).json()["id"]

    with qa_client.websocket_connect(f"/ws/session/{s_id}") as s_ws:
        _ = json.loads(s_ws.receive_text())  # initial status
        # Send malformed text on session WS -> ignored without disconnect
        s_ws.send_text("NOT_JSON{{{")
        s_ws.send_text(json.dumps({"type": "ping"}))
        assert json.loads(s_ws.receive_text())["type"] == "pong"

        with qa_client.websocket_connect(f"/ws/audio/{s_id}") as a_ws:
            # Malformed frames on audio WS
            a_ws.send_text("BROKEN_JSON")
            a_ws.send_text(json.dumps({"type": "control", "action": "unknown_action"}))
            a_ws.send_bytes(b"")
            a_ws.send_bytes(b"\x01")  # header only, no PCM payload

            # Now send valid audio -> pipeline still alive and produces transcript!
            a_ws.send_bytes(b"\x02" + _sine_pcm(0.6))
            a_ws.send_bytes(b"\x02" + _silence_pcm(0.7))

            got_transcript = None
            for _ in range(6):
                m = json.loads(s_ws.receive_text())
                if m["type"] == "transcript":
                    got_transcript = m
                    break
            assert got_transcript is not None
            assert got_transcript["text"] == "What is SQL injection?"


def test_session_recovery_restores_full_state_after_refresh(qa_client: TestClient):
    ws_manager.stt_provider_factory = lambda: EchoSTT()
    ws_manager.llm_provider_factory = lambda _p=None, _m=None: FaultyLLM("ok")
    ws_manager.auto_generate_answers = True

    s_id = qa_client.post("/api/sessions/", json={"title": "Recovery Session", "type": "technical"}).json()["id"]

    with qa_client.websocket_connect(f"/ws/session/{s_id}") as s_ws:
        _ = json.loads(s_ws.receive_text())
        with qa_client.websocket_connect(f"/ws/audio/{s_id}") as a_ws:
            a_ws.send_bytes(b"\x02" + _sine_pcm(0.6))
            a_ws.send_bytes(b"\x02" + _silence_pcm(0.7))
            for _ in range(10):
                m = json.loads(s_ws.receive_text())
                if m["type"] == "answer_complete":
                    break

    # Simulate browser reload: all REST endpoints restore persisted state completely
    assert qa_client.get(f"/api/sessions/{s_id}").status_code == 200
    assert len(qa_client.get(f"/api/sessions/{s_id}/transcript").json()) == 1
    assert len(qa_client.get(f"/api/sessions/{s_id}/questions").json()) == 1
    assert len(qa_client.get(f"/api/sessions/{s_id}/answers").json()) == 1


def test_secret_redaction_and_zero_secret_leakage(qa_client: TestClient):
    # 1. Log redaction scrubs OpenAI, Gemini, and key=val patterns
    sample = "Failed calling api_key=supersecret123 with sk-proj-abcdefghijklmnop and AIzaSyD1234567890123456789012345"
    redacted = redact_secrets(sample)
    assert "supersecret123" not in redacted
    assert "sk-proj-" not in redacted
    assert "AIzaSyD" not in redacted
    assert "[REDACTED]" in redacted

    filt = SecretRedactionFilter()
    rec = logging.LogRecord("test", logging.INFO, "", 0, "Using key %s", ("sk-1234567890abcdef1234",), None)
    assert filt.filter(rec) is True
    assert "sk-1234567890abcdef1234" not in rec.getMessage()

    # 2. Settings and health endpoints never expose raw credentials
    settings_json = json.dumps(qa_client.get("/api/settings/").json()).lower()
    health_json = json.dumps(qa_client.get("/health").json()).lower()
    for forbidden in ("google_api_key", "openai_api_key", "deepgram_api_key", "app_secret"):
        assert forbidden not in settings_json
        assert forbidden not in health_json


def test_boundary_validation_and_not_found_contracts(qa_client: TestClient):
    # Empty session title -> 422
    assert qa_client.post("/api/sessions/", json={"title": "", "type": "technical"}).status_code == 422
    # Missing session across routes -> 404
    assert qa_client.get("/api/sessions/does-not-exist").status_code == 404
    assert qa_client.get("/api/history/does-not-exist").status_code == 404
    assert qa_client.get("/api/mock/sessions/does-not-exist").status_code == 404
    assert qa_client.get("/api/knowledge-base/does-not-exist").status_code == 404
    assert qa_client.delete("/api/resume/does-not-exist").status_code == 404
    # Invalid export format -> 422
    s_id = qa_client.post("/api/sessions/", json={"title": "Val Test", "type": "general"}).json()["id"]
    assert qa_client.get(f"/api/history/{s_id}/export?format=xml").status_code == 422
    # Too-short manual question -> 422
    assert qa_client.post(f"/api/sessions/{s_id}/questions", json={"question_text": "x"}).status_code == 422
