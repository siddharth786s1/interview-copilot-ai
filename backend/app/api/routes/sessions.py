"""
Session CRUD API — create, list, get, update status, delete.
"""
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.websockets.manager import ws_manager
from app.core.exceptions import ValidationError
from app.database.connection import get_session
from app.models.session import Session, TranscriptSegment, DetectedQuestion, GeneratedAnswer
from app.schemas.session import (
    AnswerRequest,
    AnswerResponse,
    ManualQuestionCreate,
    ScreenAnalysisResponse,
    SessionCreate,
    SessionResponse,
    SessionUpdate,
)
from app.services.answer_generation.base import LLMProviderError
from app.services.answer_generation.service import extract_keywords
from app.services.vision.screen_analyzer import validate_screen_image

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(payload: SessionCreate, db: AsyncSession = Depends(get_session)):
    session = Session(
        title=payload.title,
        type=payload.type,
        status="created",
        settings_snapshot=json.dumps(payload.settings or {}),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    logger.info("Session created: %s (%s)", session.id, session.title)
    return session


@router.get("/", response_model=List[SessionResponse])
async def list_sessions(
    type: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_session),
):
    query = select(Session)
    if type:
        query = query.where(Session.type == type)
    if status:
        query = query.where(Session.status == status)
    query = query.order_by(Session.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session_by_id(session_id: str, db: AsyncSession = Depends(get_session)):
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return session


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str, payload: SessionUpdate, db: AsyncSession = Depends(get_session)
):
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    if payload.status is not None:
        session.status = payload.status
        if payload.status == "ended" and session.ended_at is None:
            session.ended_at = datetime.now(timezone.utc)
            if session.created_at:
                # Handle both offset-naive and offset-aware created_at
                created = session.created_at
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                delta = session.ended_at - created
                session.duration_seconds = max(0, int(delta.total_seconds()))
    if payload.title is not None:
        session.title = payload.title

    db.add(session)
    await db.commit()
    await db.refresh(session)

    if payload.status == "ended":
        await ws_manager.cleanup_session(session_id)

    return session


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: str, db: AsyncSession = Depends(get_session)):
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    # Cascade delete related records
    # 1. Generated answers for questions in this session
    q_result = await db.execute(select(DetectedQuestion.id).where(DetectedQuestion.session_id == session_id))
    question_ids = q_result.scalars().all()
    if question_ids:
        for qid in question_ids:
            a_res = await db.execute(select(GeneratedAnswer).where(GeneratedAnswer.question_id == qid))
            for ans in a_res.scalars().all():
                await db.delete(ans)

    # 2. Detected questions
    dq_res = await db.execute(select(DetectedQuestion).where(DetectedQuestion.session_id == session_id))
    for dq in dq_res.scalars().all():
        await db.delete(dq)

    # 3. Transcript segments
    ts_res = await db.execute(select(TranscriptSegment).where(TranscriptSegment.session_id == session_id))
    for ts in ts_res.scalars().all():
        await db.delete(ts)

    # 4. The session itself
    await db.delete(session)
    await db.commit()
    logger.info("Session deleted with cascaded records: %s", session_id)


@router.get("/{session_id}/transcript", response_model=List[TranscriptSegment])
async def get_session_transcript(session_id: str, db: AsyncSession = Depends(get_session)):
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    res = await db.execute(
        select(TranscriptSegment)
        .where(TranscriptSegment.session_id == session_id)
        .order_by(TranscriptSegment.sequence.asc())
    )
    return res.scalars().all()


@router.get("/{session_id}/questions", response_model=List[DetectedQuestion])
async def get_session_questions(session_id: str, db: AsyncSession = Depends(get_session)):
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    res = await db.execute(
        select(DetectedQuestion)
        .where(DetectedQuestion.session_id == session_id)
        .order_by(DetectedQuestion.detected_at.asc())
    )
    return res.scalars().all()


@router.post(
    "/{session_id}/questions",
    response_model=DetectedQuestion,
    status_code=status.HTTP_201_CREATED,
)
async def create_manual_question(
    session_id: str,
    payload: ManualQuestionCreate,
    db: AsyncSession = Depends(get_session),
):
    """Manual question submission fallback — persists to DB and notifies active workspace."""
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    cleaned = payload.question_text.strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail="Question text cannot be empty")

    row = DetectedQuestion(
        session_id=session_id,
        segment_ids=json.dumps([]),
        question_text=cleaned,
        question_type=payload.question_type or "manual",
        answered=False,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    # Register in live QuestionDetectionEngine context & broadcast to WebSocket clients
    q_engine = ws_manager.get_or_create_question_engine(session_id)
    q_event = q_engine.register_manual_question(cleaned, question_id=row.id)
    await ws_manager.broadcast(session_id, q_event.to_ws_dict())

    # Trigger non-blocking streaming answer generation if enabled
    if payload.auto_generate and ws_manager.auto_generate_answers:
        ws_manager.schedule_answer_generation(
            session_id=session_id,
            question_id=row.id,
            question_text=cleaned,
            question_type=row.question_type,
            style=payload.style,
        )

    logger.info("Manual question created for session %s: %s", session_id, row.id)
    return row


@router.get("/{session_id}/answers", response_model=List[AnswerResponse])
async def get_session_answers(session_id: str, db: AsyncSession = Depends(get_session)):
    """Return all generated answers associated with questions in this session."""
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    q_res = await db.execute(
        select(DetectedQuestion).where(DetectedQuestion.session_id == session_id)
    )
    questions_map = {q.id: q for q in q_res.scalars().all()}
    if not questions_map:
        return []

    a_res = await db.execute(
        select(GeneratedAnswer)
        .where(GeneratedAnswer.question_id.in_(list(questions_map.keys())))
        .order_by(GeneratedAnswer.generated_at.asc())
    )
    answers = a_res.scalars().all()
    return [
        AnswerResponse(
            id=a.id,
            question_id=a.question_id,
            style=a.style,
            answer_text=a.answer_text,
            model_used=a.model_used,
            generated_at=a.generated_at,
            generation_time_ms=a.generation_time_ms,
            keywords=extract_keywords(
                questions_map[a.question_id].question_text, a.answer_text
            ),
            needs_customization="needs customization" in a.answer_text.lower(),
        )
        for a in answers
    ]


@router.post(
    "/{session_id}/questions/{question_id}/answer",
    response_model=AnswerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_question_answer(
    session_id: str,
    question_id: str,
    payload: AnswerRequest,
    db: AsyncSession = Depends(get_session),
):
    """
    Generate, regenerate, change style, or expand an AI answer for a specific question.
    Streams chunks over /ws/session/{session_id} and returns the completed AnswerResponse.
    """
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    question = await db.get(DetectedQuestion, question_id)
    if not question or question.session_id != session_id:
        raise HTTPException(status_code=404, detail=f"Question '{question_id}' not found in session")

    expand_prev: Optional[str] = None
    if payload.expand:
        prev_res = await db.execute(
            select(GeneratedAnswer)
            .where(GeneratedAnswer.question_id == question_id)
            .order_by(GeneratedAnswer.generated_at.desc())
            .limit(1)
        )
        prev_ans = prev_res.scalar_one_or_none()
        if prev_ans:
            expand_prev = prev_ans.answer_text

    try:
        outcome = await ws_manager.generate_and_stream_answer(
            session_id=session_id,
            question_id=question_id,
            question_text=question.question_text,
            question_type=question.question_type,
            style=payload.style,
            technical_depth=payload.technical_depth,
            expand_previous_answer=expand_prev,
            raise_on_error=True,
        )
    except LLMProviderError as err:
        status_code = err.status_code or (504 if err.code == "LLM_TIMEOUT" else 503)
        raise HTTPException(
            status_code=status_code,
            detail={"code": err.code, "message": err.message},
        )

    if outcome is None:
        raise HTTPException(status_code=503, detail="Failed to generate answer")

    saved_row, gen_result = outcome
    return AnswerResponse(
        id=saved_row.id,
        question_id=saved_row.question_id,
        style=saved_row.style,
        answer_text=saved_row.answer_text,
        model_used=saved_row.model_used,
        generated_at=saved_row.generated_at,
        generation_time_ms=saved_row.generation_time_ms,
        ttft_ms=gen_result.ttft_ms,
        keywords=gen_result.keywords,
        needs_customization=gen_result.needs_customization,
    )


@router.post(
    "/{session_id}/analyze-screen",
    response_model=ScreenAnalysisResponse,
    status_code=status.HTTP_200_OK,
)
async def analyze_session_screen_endpoint(
    session_id: str,
    image: UploadFile = File(...),
    prompt: Optional[str] = Form(default=None),
    style: Optional[str] = Form(default=None),
    auto_mode: bool = Form(default=False),
    db: AsyncSession = Depends(get_session),
):
    """
    Analyze a user-shared screen snapshot (JPEG/PNG/WebP) with the multimodal LLM.
    - When auto_mode=True, only replies & creates a question/answer card if actionable
      interview content is visible on screen.
    - Always updates the session's visual screen context so subsequent voice/manual
      questions understand what is on screen.
    """
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    raw_bytes = await image.read()
    try:
        validated_mime = validate_screen_image(raw_bytes, image.content_type)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        result, q_row, a_row = await ws_manager.analyze_session_screen(
            session_id=session_id,
            image_bytes=raw_bytes,
            image_mime_type=validated_mime,
            custom_prompt=prompt,
            style=style,
            auto_mode=auto_mode,
        )
    except LLMProviderError as err:
        status_code = err.status_code or (504 if err.code == "LLM_TIMEOUT" else 503)
        raise HTTPException(
            status_code=status_code,
            detail={"code": err.code, "message": err.message},
        )

    question_payload = None
    if q_row is not None:
        question_payload = {
            "id": q_row.id,
            "session_id": q_row.session_id,
            "question_text": q_row.question_text,
            "question_type": q_row.question_type,
            "detected_at": q_row.detected_at.isoformat(),
            "answered": q_row.answered,
        }

    answer_payload = None
    if a_row is not None:
        answer_payload = AnswerResponse(
            id=a_row.id,
            question_id=a_row.question_id,
            style=a_row.style,
            answer_text=a_row.answer_text,
            model_used=a_row.model_used,
            generated_at=a_row.generated_at,
            generation_time_ms=a_row.generation_time_ms,
            ttft_ms=result.ttft_ms,
            keywords=result.keywords,
            needs_customization="needs customization" in a_row.answer_text.lower(),
        )

    return ScreenAnalysisResponse(
        actionable=result.actionable,
        topic=result.topic,
        screen_summary=result.screen_summary,
        question=question_payload,
        answer=answer_payload,
        analysis_time_ms=result.generation_time_ms,
    )
