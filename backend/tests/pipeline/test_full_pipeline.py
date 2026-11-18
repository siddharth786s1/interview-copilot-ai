"""
End-to-end Pipeline Tests:
Audio PCM -> /ws/audio -> STT -> TranscriptManager -> QuestionDetectionEngine
-> ContextManager -> AnswerGenerationService (streaming) -> /ws/session -> SQLite DB.

Covers all 7 mandatory interview questions, style switching, Expand, and error handling.
"""
import asyncio
import json
import math
import struct
from typing import AsyncIterator, List

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel

from app.api.websockets.manager import ws_manager
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


class PipelineSTT(SpeechToTextProvider):
    def __init__(self, utterances: List[str]):
        self._utterances = list(utterances)

    @property
    def name(self) -> str:
        return "pipeline-stt"

    async def transcribe_pcm(self, audio_pcm: bytes, source: str, language: str = "en", is_final: bool = True):
        if not self._utterances:
            return []
        text = self._utterances.pop(0)
        return [TranscriptChunkResult(text=text, source=source, is_final=is_final, language=language, latency_ms=5)]


class PipelineLLM(LLMProvider):
    def __init__(self, fail_error: LLMProviderError | None = None):
        self._fail_error = fail_error

    @property
    def name(self) -> str:
        return "pipeline-llm"

    @property
    def model_name(self) -> str:
        return "mock-flash"

    async def stream_generate(
        self, system_prompt: str, user_prompt: str, max_tokens: int = 800, temperature: float = 0.3
    ) -> AsyncIterator[str]:
        if self._fail_error is not None:
            raise self._fail_error
        if "TASK: EXPAND EXISTING ANSWER" in user_prompt:
            yield "Expanded deep-dive: "
            yield "Here is a concrete production example and edge cases."
            return
        if "MISSING PERSONAL CONTEXT DETECTED" in system_prompt:
            yield "[Needs customization — upload your resume for personalized details] "
            yield "Share your role, core technologies, and measurable impact."
            return
        yield "Grounded technical response: "
        yield "Parameterized queries and RBAC protect authentication and authorization."


@pytest.fixture
def pipeline_client(tmp_path):
    db_file = tmp_path / "pipeline_test.db"
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
    ws_manager.auto_generate_answers = True
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


def test_full_pipeline_audio_to_streaming_answer_for_all_seven_mandatory_questions(pipeline_client: TestClient):
    mandatory_questions = [
        "Explain the difference between authentication and authorization.",
        "What is SQL injection?",
        "Explain the SAP authorization concept.",
        "What is the difference between OTBI and BI Publisher?",
        "Explain your previous project.",
        "How would you troubleshoot an application security issue?",
        "Tell me about yourself.",
    ]

    ws_manager.stt_provider_factory = lambda: PipelineSTT(mandatory_questions)
    ws_manager.llm_provider_factory = lambda _p=None, _m=None: PipelineLLM()

    session_id = pipeline_client.post(
        "/api/sessions/", json={"title": "Full Pipeline 7Q Test", "type": "technical"}
    ).json()["id"]

    completed_answers = []

    with pipeline_client.websocket_connect(f"/ws/session/{session_id}") as session_ws:
        _ = json.loads(session_ws.receive_text())  # initial status

        with pipeline_client.websocket_connect(f"/ws/audio/{session_id}") as audio_ws:
            for expected_q in mandatory_questions:
                audio_ws.send_bytes(b"\x02" + _sine_pcm(0.6))
                audio_ws.send_bytes(b"\x02" + _silence_pcm(0.7))

                got_question = False
                chunks_received = []
                got_complete = None

                for _ in range(12):
                    ev = json.loads(session_ws.receive_text())
                    if ev["type"] == "question":
                        assert ev["text"] == expected_q
                        got_question = True
                    elif ev["type"] == "answer_chunk":
                        chunks_received.append(ev["text"])
                    elif ev["type"] == "answer_complete":
                        got_complete = ev
                        break

                assert got_question is True, f"Missed question: {expected_q}"
                assert len(chunks_received) >= 2, f"Expected streaming chunks for: {expected_q}"
                assert got_complete is not None
                assert got_complete["full_text"] == "".join(chunks_received).strip()
                completed_answers.append((expected_q, got_complete))

    # Verify personal questions flagged needs_customization=True (no resume uploaded)
    by_q = dict(completed_answers)
    assert by_q["Explain your previous project."]["needs_customization"] is True
    assert by_q["Tell me about yourself."]["needs_customization"] is True
    assert by_q["What is SQL injection?"]["needs_customization"] is False

    # Verify all 7 questions and 7 answers persisted cleanly in SQLite
    q_rows = pipeline_client.get(f"/api/sessions/{session_id}/questions").json()
    a_rows = pipeline_client.get(f"/api/sessions/{session_id}/answers").json()
    assert len(q_rows) == 7
    assert len(a_rows) == 7
    assert all(q["answered"] is True for q in q_rows)


def test_rest_style_switch_expand_and_error_handling(pipeline_client: TestClient):
    ws_manager.llm_provider_factory = lambda _p=None, _m=None: PipelineLLM()

    session_id = pipeline_client.post(
        "/api/sessions/", json={"title": "Style & Expand Test", "type": "technical"}
    ).json()["id"]

    # Create manual question without auto-generation, then test explicit styles & expand
    q_resp = pipeline_client.post(
        f"/api/sessions/{session_id}/questions",
        json={"question_text": "What is SQL injection?", "auto_generate": False},
    )
    assert q_resp.status_code == 201
    q_id = q_resp.json()["id"]

    for style in ("short", "detailed", "practical", "stepbystep"):
        ans_resp = pipeline_client.post(
            f"/api/sessions/{session_id}/questions/{q_id}/answer",
            json={"style": style, "technical_depth": "high"},
        )
        assert ans_resp.status_code == 201
        body = ans_resp.json()
        assert body["style"] == style
        assert body["answer_text"]
        assert body["ttft_ms"] is not None

    # Expand existing answer
    exp_resp = pipeline_client.post(
        f"/api/sessions/{session_id}/questions/{q_id}/answer",
        json={"style": "detailed", "expand": True},
    )
    assert exp_resp.status_code == 201
    assert "Expanded deep-dive" in exp_resp.json()["answer_text"]

    # Inject provider 429 rate-limit error -> returns structured 429
    ws_manager.llm_provider_factory = lambda _p=None, _m=None: PipelineLLM(
        fail_error=LLMProviderError("gemini", "Rate limit exceeded", code="LLM_RATE_LIMIT", retryable=False, status_code=429)
    )
    err_resp = pipeline_client.post(
        f"/api/sessions/{session_id}/questions/{q_id}/answer",
        json={"style": "short"},
    )
    assert err_resp.status_code == 429
    assert err_resp.json()["detail"]["code"] == "LLM_RATE_LIMIT"
