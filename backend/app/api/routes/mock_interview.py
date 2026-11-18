"""
Mock Interview API — Independent practice workflow backed strictly by
`mock_sessions` and `mock_exchanges` tables (never touches live `sessions`).
"""
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.websockets.manager import ws_manager
from app.database.connection import get_session
from app.models.mock import MockExchange, MockSession
from app.models.settings import AppSettings
from app.services.mock_interview.engine import MockInterviewEngine

logger = logging.getLogger(__name__)
router = APIRouter()


class MockSessionCreate(BaseModel):
    topic: str = Field(min_length=2, max_length=200)


class MockAnswerSubmit(BaseModel):
    user_answer: str = Field(min_length=1, max_length=10000)


class MockExchangeResponse(BaseModel):
    id: str
    mock_session_id: str
    question_text: str
    user_answer: Optional[str] = None
    evaluation: Optional[dict] = None
    created_at: datetime


class MockSessionSummary(BaseModel):
    id: str
    topic: str
    created_at: datetime
    ended_at: Optional[datetime] = None
    question_count: int
    answered_count: int
    average_score: Optional[float] = None


class MockSessionDetail(BaseModel):
    session: MockSessionSummary
    exchanges: List[MockExchangeResponse]


class MockPerformanceSummary(BaseModel):
    total_sessions: int
    total_evaluated: int
    overall_average_score: Optional[float] = None
    by_topic: List[dict]
    score_trend: List[dict]


def _parse_eval(raw: Optional[str]) -> Optional[dict]:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _to_exchange_resp(row: MockExchange) -> MockExchangeResponse:
    return MockExchangeResponse(
        id=row.id,
        mock_session_id=row.mock_session_id,
        question_text=row.question_text,
        user_answer=row.user_answer,
        evaluation=_parse_eval(row.evaluation),
        created_at=row.created_at,
    )


async def _build_mock_summary(db: AsyncSession, session: MockSession) -> MockSessionSummary:
    exchanges = (
        await db.execute(
            select(MockExchange)
            .where(MockExchange.mock_session_id == session.id)
            .order_by(MockExchange.created_at.asc())
        )
    ).scalars().all()

    scores = []
    answered = 0
    for ex in exchanges:
        if ex.user_answer:
            answered += 1
        ev = _parse_eval(ex.evaluation)
        if ev and isinstance(ev.get("score"), (int, float)):
            scores.append(float(ev["score"]))

    avg = round(sum(scores) / len(scores), 1) if scores else None
    return MockSessionSummary(
        id=session.id,
        topic=session.topic,
        created_at=session.created_at,
        ended_at=session.ended_at,
        question_count=len(exchanges),
        answered_count=answered,
        average_score=avg,
    )


async def _get_engine_and_prefs(db: AsyncSession):
    cfg = (await db.execute(select(AppSettings).where(AppSettings.id == 1))).scalar_one_or_none()
    provider_name = cfg.llm_provider if cfg else None
    model_name = cfg.llm_model if cfg else None
    engine = MockInterviewEngine(llm_provider_factory=ws_manager.llm_provider_factory)
    return engine, provider_name, model_name


@router.get("/performance", response_model=MockPerformanceSummary)
async def get_mock_performance(db: AsyncSession = Depends(get_session)):
    sessions = (
        await db.execute(select(MockSession).order_by(MockSession.created_at.asc()))
    ).scalars().all()

    all_scores: List[float] = []
    topic_scores: Dict[str, List[float]] = {}
    trend: List[dict] = []

    for s in sessions:
        summary = await _build_mock_summary(db, s)
        if summary.average_score is not None:
            trend.append(
                {
                    "mock_session_id": s.id,
                    "topic": s.topic,
                    "date": s.created_at.isoformat(),
                    "average_score": summary.average_score,
                    "answered_count": summary.answered_count,
                }
            )
            topic_scores.setdefault(s.topic, []).append(summary.average_score)

        exchanges = (
            await db.execute(select(MockExchange).where(MockExchange.mock_session_id == s.id))
        ).scalars().all()
        for ex in exchanges:
            ev = _parse_eval(ex.evaluation)
            if ev and isinstance(ev.get("score"), (int, float)):
                all_scores.append(float(ev["score"]))

    by_topic = [
        {
            "topic": topic,
            "sessions": len(vals),
            "average_score": round(sum(vals) / len(vals), 1),
        }
        for topic, vals in topic_scores.items()
    ]

    overall = round(sum(all_scores) / len(all_scores), 1) if all_scores else None
    return MockPerformanceSummary(
        total_sessions=len(sessions),
        total_evaluated=len(all_scores),
        overall_average_score=overall,
        by_topic=by_topic,
        score_trend=trend,
    )


@router.get("/sessions", response_model=List[MockSessionSummary])
async def list_mock_sessions(db: AsyncSession = Depends(get_session)):
    sessions = (
        await db.execute(select(MockSession).order_by(MockSession.created_at.desc()))
    ).scalars().all()
    return [await _build_mock_summary(db, s) for s in sessions]


@router.post("/sessions", response_model=MockSessionDetail, status_code=status.HTTP_201_CREATED)
async def create_mock_session(payload: MockSessionCreate, db: AsyncSession = Depends(get_session)):
    mock_session = MockSession(topic=payload.topic.strip())
    db.add(mock_session)
    await db.commit()
    await db.refresh(mock_session)

    engine, provider_name, model_name = await _get_engine_and_prefs(db)
    q_res = await engine.generate_question(
        topic=mock_session.topic,
        previous_questions=[],
        provider_name=provider_name,
        model_name=model_name,
    )

    first_exchange = MockExchange(
        mock_session_id=mock_session.id,
        question_text=q_res.question_text,
    )
    db.add(first_exchange)
    await db.commit()
    await db.refresh(first_exchange)

    summary = await _build_mock_summary(db, mock_session)
    return MockSessionDetail(session=summary, exchanges=[_to_exchange_resp(first_exchange)])


@router.get("/sessions/{mock_session_id}", response_model=MockSessionDetail)
async def get_mock_session(mock_session_id: str, db: AsyncSession = Depends(get_session)):
    mock_session = await db.get(MockSession, mock_session_id)
    if not mock_session:
        raise HTTPException(status_code=404, detail=f"Mock session '{mock_session_id}' not found")

    exchanges = (
        await db.execute(
            select(MockExchange)
            .where(MockExchange.mock_session_id == mock_session_id)
            .order_by(MockExchange.created_at.asc())
        )
    ).scalars().all()

    summary = await _build_mock_summary(db, mock_session)
    return MockSessionDetail(
        session=summary,
        exchanges=[_to_exchange_resp(ex) for ex in exchanges],
    )


@router.post(
    "/sessions/{mock_session_id}/next-question",
    response_model=MockExchangeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_next_mock_question(
    mock_session_id: str, db: AsyncSession = Depends(get_session)
):
    mock_session = await db.get(MockSession, mock_session_id)
    if not mock_session:
        raise HTTPException(status_code=404, detail=f"Mock session '{mock_session_id}' not found")

    prev_rows = (
        await db.execute(
            select(MockExchange)
            .where(MockExchange.mock_session_id == mock_session_id)
            .order_by(MockExchange.created_at.asc())
        )
    ).scalars().all()
    prev_questions = [r.question_text for r in prev_rows]

    engine, provider_name, model_name = await _get_engine_and_prefs(db)
    q_res = await engine.generate_question(
        topic=mock_session.topic,
        previous_questions=prev_questions,
        provider_name=provider_name,
        model_name=model_name,
    )

    exchange = MockExchange(
        mock_session_id=mock_session_id,
        question_text=q_res.question_text,
    )
    db.add(exchange)
    await db.commit()
    await db.refresh(exchange)
    return _to_exchange_resp(exchange)


@router.post(
    "/sessions/{mock_session_id}/exchanges/{exchange_id}/answer",
    response_model=MockExchangeResponse,
)
async def submit_mock_answer(
    mock_session_id: str,
    exchange_id: str,
    payload: MockAnswerSubmit,
    db: AsyncSession = Depends(get_session),
):
    mock_session = await db.get(MockSession, mock_session_id)
    if not mock_session:
        raise HTTPException(status_code=404, detail=f"Mock session '{mock_session_id}' not found")

    exchange = await db.get(MockExchange, exchange_id)
    if not exchange or exchange.mock_session_id != mock_session_id:
        raise HTTPException(status_code=404, detail=f"Exchange '{exchange_id}' not found")

    engine, provider_name, model_name = await _get_engine_and_prefs(db)
    eval_result = await engine.evaluate_answer(
        topic=mock_session.topic,
        question_text=exchange.question_text,
        user_answer=payload.user_answer.strip(),
        provider_name=provider_name,
        model_name=model_name,
    )

    exchange.user_answer = payload.user_answer.strip()
    exchange.evaluation = json.dumps(eval_result.to_dict())
    db.add(exchange)
    await db.commit()
    await db.refresh(exchange)
    return _to_exchange_resp(exchange)


@router.post("/sessions/{mock_session_id}/end", response_model=MockSessionSummary)
async def end_mock_session(mock_session_id: str, db: AsyncSession = Depends(get_session)):
    mock_session = await db.get(MockSession, mock_session_id)
    if not mock_session:
        raise HTTPException(status_code=404, detail=f"Mock session '{mock_session_id}' not found")
    mock_session.ended_at = datetime.now(timezone.utc)
    db.add(mock_session)
    await db.commit()
    await db.refresh(mock_session)
    return await _build_mock_summary(db, mock_session)


@router.delete("/sessions/{mock_session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mock_session(mock_session_id: str, db: AsyncSession = Depends(get_session)):
    mock_session = await db.get(MockSession, mock_session_id)
    if not mock_session:
        raise HTTPException(status_code=404, detail=f"Mock session '{mock_session_id}' not found")

    exchanges = (
        await db.execute(select(MockExchange).where(MockExchange.mock_session_id == mock_session_id))
    ).scalars().all()
    for ex in exchanges:
        await db.delete(ex)
    await db.delete(mock_session)
    await db.commit()


@router.post("/transcribe")
async def transcribe_spoken_mock_answer(request: Request):
    """Transcribe raw 16kHz 16-bit mono PCM spoken mock answer via the configured STT provider."""
    pcm = await request.body()
    if not pcm or len(pcm) < 3200:
        raise HTTPException(status_code=400, detail="Audio recording too short to transcribe.")
    stt = ws_manager.stt_provider_factory()
    results = await stt.transcribe_pcm(pcm, source="mic", language="en", is_final=True)
    text = " ".join(r.text.strip() for r in results if r.text.strip()).strip()
    return {"text": text}
