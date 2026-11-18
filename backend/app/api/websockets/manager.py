"""
SessionConnectionManager — Manages active WebSocket connections and per-session
real-time transcription, question detection, and streaming AI answer pipelines.
"""
import asyncio
import json
import logging
from typing import Callable, Dict, Optional, Set
from fastapi import WebSocket
from sqlmodel import select

from app.database.connection import AsyncSessionLocal
from app.models.session import (
    DetectedQuestion,
    GeneratedAnswer,
    TranscriptSegment,
)
from app.models.settings import AppSettings
from app.services.answer_generation.base import (
    AnswerGenerationResult,
    LLMProvider,
    LLMProviderError,
)
from app.services.answer_generation.context_manager import ContextManager
from app.services.answer_generation.factory import get_llm_provider
from app.services.answer_generation.service import AnswerGenerationService
from app.services.question_detection.engine import (
    DetectedQuestionEvent,
    QuestionDetectionEngine,
)
from app.services.transcription.base import SpeechToTextProvider
from app.services.transcription.factory import get_stt_provider
from app.services.transcription.transcript_manager import (
    ManagedTranscriptEvent,
    TranscriptManager,
)
from app.services.vision.screen_analyzer import (
    ScreenAnalysisResult,
    ScreenAnalyzerService,
)

logger = logging.getLogger(__name__)


class SessionConnectionManager:
    """
    Coordinates /ws/session/{session_id} subscribers, /ws/audio/{session_id}
    transcription managers, QuestionDetectionEngine, streaming AnswerGenerationService,
    and permitted visual ScreenAnalyzerService.
    """

    def __init__(self):
        self._session_sockets: Dict[str, Set[WebSocket]] = {}
        self._transcript_managers: Dict[str, TranscriptManager] = {}
        self._question_engines: Dict[str, QuestionDetectionEngine] = {}
        self._audio_sources: Dict[str, Dict[str, bool]] = {}
        self._answer_tasks: Dict[str, Set[asyncio.Task]] = {}
        self._screen_context: Dict[str, str] = {}
        self.context_manager = ContextManager()
        # Overridable hooks for dependency injection in tests
        self.stt_provider_factory: Callable[[], SpeechToTextProvider] = get_stt_provider
        self.llm_provider_factory: Callable[[Optional[str], Optional[str]], LLMProvider] = get_llm_provider
        self.db_session_factory = AsyncSessionLocal
        self.auto_generate_answers: bool = True

    def set_screen_context(self, session_id: str, summary: str) -> None:
        cleaned = summary.strip()
        if cleaned:
            self._screen_context[session_id] = cleaned[:1000]

    def get_screen_context(self, session_id: str) -> Optional[str]:
        return self._screen_context.get(session_id)

    async def connect_session_ws(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        if session_id not in self._session_sockets:
            self._session_sockets[session_id] = set()
        self._session_sockets[session_id].add(websocket)
        logger.info(
            "Session WS connected: session=%s (total=%d)",
            session_id,
            len(self._session_sockets[session_id]),
        )

        sources = self._audio_sources.get(session_id, {"tab": False, "mic": False})
        tm = self._transcript_managers.get(session_id)
        await self._safe_send(
            websocket,
            {
                "type": "status",
                "session_id": session_id,
                "session_status": "paused" if (tm and tm.paused) else "active",
                "audio_sources": sources,
                "language": tm.language if tm else "en",
            },
        )

    def disconnect_session_ws(self, session_id: str, websocket: WebSocket) -> None:
        sockets = self._session_sockets.get(session_id)
        if sockets:
            sockets.discard(websocket)
            if not sockets:
                del self._session_sockets[session_id]
        logger.info("Session WS disconnected: session=%s", session_id)

    async def broadcast(self, session_id: str, payload: dict) -> None:
        sockets = list(self._session_sockets.get(session_id, set()))
        if not sockets:
            return
        message = json.dumps(payload)
        dead: list[WebSocket] = []
        for ws in sockets:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect_session_ws(session_id, ws)

    async def _safe_send(self, websocket: WebSocket, payload: dict) -> None:
        try:
            await websocket.send_text(json.dumps(payload))
        except Exception:
            pass

    def get_or_create_question_engine(self, session_id: str) -> QuestionDetectionEngine:
        if session_id not in self._question_engines:
            self._question_engines[session_id] = QuestionDetectionEngine(session_id=session_id)
        return self._question_engines[session_id]

    def _register_answer_task(self, session_id: str, task: asyncio.Task) -> None:
        tasks = self._answer_tasks.setdefault(session_id, set())
        tasks.add(task)
        task.add_done_callback(lambda t: tasks.discard(t))

    def cancel_answer_tasks(self, session_id: str) -> int:
        tasks = list(self._answer_tasks.pop(session_id, set()))
        cancelled = 0
        for task in tasks:
            if not task.done():
                task.cancel()
                cancelled += 1
        return cancelled

    async def generate_and_stream_answer(
        self,
        session_id: str,
        question_id: str,
        question_text: str,
        question_type: str = "direct",
        style: Optional[str] = None,
        technical_depth: Optional[str] = None,
        expand_previous_answer: Optional[str] = None,
        raise_on_error: bool = False,
    ) -> Optional[tuple[GeneratedAnswer, AnswerGenerationResult]]:
        """
        Build context, stream tokens over /ws/session/{session_id}, persist
        GeneratedAnswer to SQLite, and broadcast answer_complete.
        """
        async with self.db_session_factory() as db:
            # Read persisted user preferences if not overridden
            settings_res = await db.execute(select(AppSettings).where(AppSettings.id == 1))
            app_cfg = settings_res.scalar_one_or_none()

            resolved_style = style or (app_cfg.default_answer_style if app_cfg else "short")
            resolved_depth = technical_depth or (app_cfg.default_technical_depth if app_cfg else "medium")
            provider_name = app_cfg.llm_provider if app_cfg else None
            model_name = app_cfg.llm_model if app_cfg else None

            ctx = await self.context_manager.build_context(
                db=db,
                session_id=session_id,
                question_id=question_id,
                question_text=question_text,
                question_type=question_type,
                style=resolved_style,
                technical_depth=resolved_depth,
                expand_previous_answer=expand_previous_answer,
                screen_context=self.get_screen_context(session_id),
            )

        provider = self.llm_provider_factory(provider_name, model_name)
        service = AnswerGenerationService(
            provider=provider,
            context_manager=self.context_manager,
        )

        await self.broadcast(
            session_id,
            {
                "type": "answer_start",
                "session_id": session_id,
                "question_id": question_id,
                "style": ctx.style,
                "needs_customization": ctx.needs_customization,
            },
        )

        async def _on_chunk(qid: str, token: str) -> None:
            await self.broadcast(
                session_id,
                {
                    "type": "answer_chunk",
                    "session_id": session_id,
                    "question_id": qid,
                    "text": token,
                },
            )

        try:
            result = await service.generate_answer(ctx, on_chunk=_on_chunk)
        except asyncio.CancelledError:
            logger.info("Streamed answer cancelled for session=%s question=%s", session_id, question_id)
            raise
        except LLMProviderError as err:
            await self.broadcast(
                session_id,
                {
                    "type": "error",
                    "code": err.code,
                    "question_id": question_id,
                    "message": err.message,
                },
            )
            if raise_on_error:
                raise
            return None
        except Exception as exc:
            logger.error("Unexpected answer generation error: %s", exc)
            await self.broadcast(
                session_id,
                {
                    "type": "error",
                    "code": "LLM_PROVIDER_ERROR",
                    "question_id": question_id,
                    "message": "Unexpected error while generating answer.",
                },
            )
            if raise_on_error:
                raise
            return None

        # Persist GeneratedAnswer durably BEFORE broadcasting answer_complete
        saved_row = GeneratedAnswer(
            question_id=question_id,
            style=result.style,
            answer_text=result.answer_text,
            model_used=result.model_used,
            generation_time_ms=result.generation_time_ms,
        )
        try:
            async with self.db_session_factory() as db:
                db.add(saved_row)
                q_row = await db.get(DetectedQuestion, question_id)
                if q_row is not None:
                    q_row.answered = True
                    db.add(q_row)
                await db.commit()
                await db.refresh(saved_row)
        except Exception as e:
            logger.error("Failed to persist generated answer for question %s: %s", question_id, e)

        await self.broadcast(
            session_id,
            {
                "type": "answer_complete",
                "session_id": session_id,
                "question_id": question_id,
                "answer_id": saved_row.id,
                "style": result.style,
                "full_text": result.answer_text,
                "model_used": result.model_used,
                "ttft_ms": result.ttft_ms,
                "generation_ms": result.generation_time_ms,
                "keywords": result.keywords,
                "needs_customization": result.needs_customization,
                "generated_at": saved_row.generated_at.isoformat(),
            },
        )
        return saved_row, result

    def schedule_answer_generation(
        self,
        session_id: str,
        question_id: str,
        question_text: str,
        question_type: str = "direct",
        style: Optional[str] = None,
    ) -> asyncio.Task:
        """Launch non-blocking background answer generation for a detected question."""
        task = asyncio.create_task(
            self.generate_and_stream_answer(
                session_id=session_id,
                question_id=question_id,
                question_text=question_text,
                question_type=question_type,
                style=style,
                raise_on_error=False,
            )
        )
        self._register_answer_task(session_id, task)
        return task

    async def _persist_and_broadcast_question(self, q_event: DetectedQuestionEvent) -> None:
        try:
            async with self.db_session_factory() as db:
                row = DetectedQuestion(
                    id=q_event.id,
                    session_id=q_event.session_id,
                    segment_ids=json.dumps(q_event.segment_ids),
                    question_text=q_event.question_text,
                    question_type=q_event.question_type,
                    detected_at=q_event.detected_at,
                    answered=False,
                )
                db.add(row)
                await db.commit()
        except Exception as e:
            logger.error(
                "Failed to persist detected question for session %s: %s",
                q_event.session_id,
                e,
            )

        await self.broadcast(q_event.session_id, q_event.to_ws_dict())

        # Trigger non-blocking AI answer generation automatically
        if self.auto_generate_answers:
            self.schedule_answer_generation(
                session_id=q_event.session_id,
                question_id=q_event.id,
                question_text=q_event.question_text,
                question_type=q_event.question_type,
            )

    def get_or_create_transcript_manager(
        self,
        session_id: str,
        language: str = "en",
    ) -> TranscriptManager:
        if session_id not in self._transcript_managers:
            provider = self.stt_provider_factory()
            q_engine = self.get_or_create_question_engine(session_id)

            async def handle_event(event: ManagedTranscriptEvent) -> None:
                segment_id: Optional[str] = None
                if event.is_final:
                    try:
                        async with self.db_session_factory() as db:
                            row = TranscriptSegment(
                                session_id=event.session_id,
                                source=event.source,
                                speaker_label=event.speaker_label,
                                text=event.text,
                                is_final=True,
                                timestamp=event.timestamp,
                                sequence=event.sequence,
                            )
                            db.add(row)
                            await db.commit()
                            segment_id = row.id
                    except Exception as e:
                        logger.error(
                            "Failed to persist transcript segment for session %s: %s",
                            session_id,
                            e,
                        )

                await self.broadcast(session_id, event.to_ws_dict())

                if event.is_final:
                    sources = self._audio_sources.get(session_id, {"tab": False, "mic": False})
                    tab_is_active = bool(sources.get("tab"))
                    if event.source == "mic" and tab_is_active:
                        q_engine.record_user_speech(event.text)
                    else:
                        q_event = q_engine.process_segment(
                            text=event.text,
                            source=event.source,
                            segment_id=segment_id,
                        )
                        if q_event is not None:
                            await self._persist_and_broadcast_question(q_event)

            self._transcript_managers[session_id] = TranscriptManager(
                session_id=session_id,
                stt_provider=provider,
                language=language,
                on_event=handle_event,
            )
            self._audio_sources.setdefault(session_id, {"tab": False, "mic": False})
        return self._transcript_managers[session_id]

    async def set_audio_source_state(
        self, session_id: str, source: str, active: bool
    ) -> None:
        sources = self._audio_sources.setdefault(session_id, {"tab": False, "mic": False})
        if sources.get(source) != active:
            sources[source] = active
            tm = self._transcript_managers.get(session_id)
            await self.broadcast(
                session_id,
                {
                    "type": "status",
                    "session_id": session_id,
                    "session_status": "paused" if (tm and tm.paused) else "active",
                    "audio_sources": dict(sources),
                    "language": tm.language if tm else "en",
                },
            )

    async def analyze_session_screen(
        self,
        session_id: str,
        image_bytes: bytes,
        image_mime_type: str,
        custom_prompt: Optional[str] = None,
        style: Optional[str] = None,
        auto_mode: bool = False,
    ) -> tuple[ScreenAnalysisResult, Optional[DetectedQuestion], Optional[GeneratedAnswer]]:
        """
        Analyze a permitted user-shared screen snapshot for the active session.

        Always refreshes the session's visual screen context so subsequent voice/manual
        questions are screen-aware. When result.actionable is True, persists a
        DetectedQuestion(question_type="screen") and GeneratedAnswer to SQLite,
        registers it in QuestionDetectionEngine, and broadcasts question + answer_complete
        over /ws/session/{session_id}.
        """
        async with self.db_session_factory() as db:
            settings_res = await db.execute(select(AppSettings).where(AppSettings.id == 1))
            app_cfg = settings_res.scalar_one_or_none()

            resolved_style = style or (app_cfg.default_answer_style if app_cfg else "short")
            resolved_depth = app_cfg.default_technical_depth if app_cfg else "medium"
            provider_name = app_cfg.llm_provider if app_cfg else None
            model_name = app_cfg.llm_model if app_cfg else None

            ctx = await self.context_manager.build_context(
                db=db,
                session_id=session_id,
                question_id="screen-pending",
                question_text=(custom_prompt.strip() if custom_prompt and custom_prompt.strip() else "Analyze shared screen"),
                question_type="screen",
                style=resolved_style,
                technical_depth=resolved_depth,
                screen_context=self.get_screen_context(session_id),
            )

        provider = self.llm_provider_factory(provider_name, model_name)
        analyzer = ScreenAnalyzerService(
            provider=provider,
            context_manager=self.context_manager,
        )

        result = await analyzer.analyze_screen(
            image_bytes=image_bytes,
            image_mime_type=image_mime_type,
            context=ctx,
            custom_prompt=custom_prompt,
            auto_mode=auto_mode,
        )

        # Always keep the latest screen summary available to voice/manual Q&A
        self.set_screen_context(session_id, result.screen_summary)

        if not result.actionable:
            return result, None, None

        question_row = DetectedQuestion(
            session_id=session_id,
            segment_ids=json.dumps([]),
            question_text=result.topic,
            question_type="screen",
            answered=True,
        )
        answer_row: Optional[GeneratedAnswer] = None

        async with self.db_session_factory() as db:
            db.add(question_row)
            await db.flush()
            answer_row = GeneratedAnswer(
                question_id=question_row.id,
                style=result.style,
                answer_text=result.answer_text,
                model_used=result.model_used,
                generation_time_ms=result.generation_time_ms,
            )
            db.add(answer_row)
            await db.commit()
            await db.refresh(question_row)
            await db.refresh(answer_row)

        # Register into QuestionDetectionEngine so voice follow-ups ("How do I optimize that?") link properly
        q_engine = self.get_or_create_question_engine(session_id)
        q_event = q_engine.register_manual_question(
            question_row.question_text,
            question_id=question_row.id,
            question_type="screen",
        )
        await self.broadcast(session_id, q_event.to_ws_dict())
        await self.broadcast(
            session_id,
            {
                "type": "answer_complete",
                "session_id": session_id,
                "question_id": question_row.id,
                "answer_id": answer_row.id,
                "style": result.style,
                "full_text": result.answer_text,
                "model_used": result.model_used,
                "ttft_ms": result.ttft_ms,
                "generation_ms": result.generation_time_ms,
                "keywords": result.keywords,
                "needs_customization": "needs customization" in result.answer_text.lower(),
                "generated_at": answer_row.generated_at.isoformat(),
            },
        )
        return result, question_row, answer_row

    async def cleanup_session(self, session_id: str) -> None:
        # Cancel any in-flight LLM generations immediately
        self.cancel_answer_tasks(session_id)
        tm = self._transcript_managers.pop(session_id, None)
        if tm:
            try:
                await tm.flush()
            except Exception as e:
                logger.warning("Error flushing session %s during cleanup: %s", session_id, e)
        self._question_engines.pop(session_id, None)
        self._audio_sources.pop(session_id, None)
        self._screen_context.pop(session_id, None)


# Singleton instance shared by audio_ws, session_ws, and REST routes
ws_manager = SessionConnectionManager()
