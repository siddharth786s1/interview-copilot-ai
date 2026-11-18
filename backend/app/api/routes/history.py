"""
Interview History API — list live sessions with counts, open full transcript + Q&A,
search past questions, export Markdown/JSON notes, delete individual sessions,
and enforce retention-based deletion.

Strictly reads/writes live `sessions` tables — never mixes `mock_sessions`.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.database.connection import get_session
from app.models.session import (
    DetectedQuestion,
    GeneratedAnswer,
    Session,
    TranscriptSegment,
)
from app.models.settings import AppSettings

logger = logging.getLogger(__name__)
router = APIRouter()


class HistorySessionItem(BaseModel):
    id: str
    title: str
    type: str
    status: str
    created_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    transcript_count: int
    question_count: int
    answer_count: int


class HistoryQAItem(BaseModel):
    question_id: str
    question_text: str
    question_type: str
    detected_at: datetime
    answers: List[dict]


class HistorySessionDetail(BaseModel):
    session: HistorySessionItem
    transcript: List[dict]
    qa_pairs: List[HistoryQAItem]


class HistorySearchHit(BaseModel):
    session_id: str
    session_title: str
    session_type: str
    session_created_at: datetime
    question_id: str
    question_text: str
    question_type: str
    detected_at: datetime
    latest_answer: Optional[str] = None


class RetentionPurgeResult(BaseModel):
    retention_days: Optional[int]
    deleted_sessions: int
    cutoff: Optional[str] = None


async def cascade_delete_session_rows(db: AsyncSession, session_id: str) -> None:
    """Delete all child rows and the parent Session row atomically."""
    q_res = await db.execute(
        select(DetectedQuestion).where(DetectedQuestion.session_id == session_id)
    )
    questions = q_res.scalars().all()
    for q in questions:
        a_res = await db.execute(
            select(GeneratedAnswer).where(GeneratedAnswer.question_id == q.id)
        )
        for ans in a_res.scalars().all():
            await db.delete(ans)
        await db.delete(q)

    t_res = await db.execute(
        select(TranscriptSegment).where(TranscriptSegment.session_id == session_id)
    )
    for ts in t_res.scalars().all():
        await db.delete(ts)

    session = await db.get(Session, session_id)
    if session:
        await db.delete(session)


async def _build_session_item(db: AsyncSession, s: Session) -> HistorySessionItem:
    t_rows = (
        await db.execute(select(TranscriptSegment.id).where(TranscriptSegment.session_id == s.id))
    ).scalars().all()
    q_ids = (
        await db.execute(select(DetectedQuestion.id).where(DetectedQuestion.session_id == s.id))
    ).scalars().all()
    a_count = 0
    if q_ids:
        a_rows = (
            await db.execute(select(GeneratedAnswer.id).where(GeneratedAnswer.question_id.in_(list(q_ids))))
        ).scalars().all()
        a_count = len(a_rows)

    return HistorySessionItem(
        id=s.id,
        title=s.title,
        type=s.type,
        status=s.status,
        created_at=s.created_at,
        ended_at=s.ended_at,
        duration_seconds=s.duration_seconds,
        transcript_count=len(t_rows),
        question_count=len(q_ids),
        answer_count=a_count,
    )


async def _build_session_detail(db: AsyncSession, s: Session) -> HistorySessionDetail:
    item = await _build_session_item(db, s)

    t_res = await db.execute(
        select(TranscriptSegment)
        .where(TranscriptSegment.session_id == s.id)
        .order_by(TranscriptSegment.sequence.asc())
    )
    transcript = [
        {
            "id": t.id,
            "source": t.source,
            "speaker_label": t.speaker_label or ("Interviewer" if t.source == "tab" else "Me"),
            "text": t.text,
            "timestamp": t.timestamp.isoformat(),
            "sequence": t.sequence,
        }
        for t in t_res.scalars().all()
    ]

    q_res = await db.execute(
        select(DetectedQuestion)
        .where(DetectedQuestion.session_id == s.id)
        .order_by(DetectedQuestion.detected_at.asc())
    )
    qa_pairs: List[HistoryQAItem] = []
    for q in q_res.scalars().all():
        a_res = await db.execute(
            select(GeneratedAnswer)
            .where(GeneratedAnswer.question_id == q.id)
            .order_by(GeneratedAnswer.generated_at.asc())
        )
        answers = [
            {
                "id": a.id,
                "style": a.style,
                "answer_text": a.answer_text,
                "model_used": a.model_used,
                "generated_at": a.generated_at.isoformat(),
                "generation_time_ms": a.generation_time_ms,
            }
            for a in a_res.scalars().all()
        ]
        qa_pairs.append(
            HistoryQAItem(
                question_id=q.id,
                question_text=q.question_text,
                question_type=q.question_type,
                detected_at=q.detected_at,
                answers=answers,
            )
        )

    return HistorySessionDetail(session=item, transcript=transcript, qa_pairs=qa_pairs)


@router.get("/", response_model=List[HistorySessionItem])
async def list_history(
    type: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_session),
):
    stmt = select(Session)
    if type and type.lower() != "all":
        stmt = stmt.where(Session.type == type)
    stmt = stmt.order_by(Session.created_at.desc())
    sessions = (await db.execute(stmt)).scalars().all()
    return [await _build_session_item(db, s) for s in sessions]


@router.get("/search", response_model=List[HistorySearchHit])
async def search_past_questions(
    q: str = Query(..., min_length=1, max_length=300),
    db: AsyncSession = Depends(get_session),
):
    needle = q.strip().lower()
    sessions = {s.id: s for s in (await db.execute(select(Session))).scalars().all()}
    questions = (
        await db.execute(select(DetectedQuestion).order_by(DetectedQuestion.detected_at.desc()))
    ).scalars().all()

    hits: List[HistorySearchHit] = []
    for dq in questions:
        sess = sessions.get(dq.session_id)
        if not sess:
            continue
        a_res = await db.execute(
            select(GeneratedAnswer)
            .where(GeneratedAnswer.question_id == dq.id)
            .order_by(GeneratedAnswer.generated_at.desc())
            .limit(1)
        )
        latest_ans = a_res.scalar_one_or_none()
        ans_text = latest_ans.answer_text if latest_ans else None

        if (
            needle in dq.question_text.lower()
            or needle in sess.title.lower()
            or (ans_text and needle in ans_text.lower())
        ):
            hits.append(
                HistorySearchHit(
                    session_id=sess.id,
                    session_title=sess.title,
                    session_type=sess.type,
                    session_created_at=sess.created_at,
                    question_id=dq.id,
                    question_text=dq.question_text,
                    question_type=dq.question_type,
                    detected_at=dq.detected_at,
                    latest_answer=ans_text,
                )
            )
    return hits


@router.post("/purge-retention", response_model=RetentionPurgeResult)
async def purge_expired_sessions(
    days_override: Optional[int] = Query(default=None, ge=0),
    db: AsyncSession = Depends(get_session),
):
    """Delete live sessions older than the configured retention_days policy."""
    retention_days = days_override
    if retention_days is None:
        cfg = (await db.execute(select(AppSettings).where(AppSettings.id == 1))).scalar_one_or_none()
        retention_days = cfg.retention_days if cfg else None

    if retention_days is None:
        return RetentionPurgeResult(retention_days=None, deleted_sessions=0, cutoff=None)

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    all_sessions = (await db.execute(select(Session))).scalars().all()

    deleted = 0
    for s in all_sessions:
        created = s.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if created <= cutoff:
            await cascade_delete_session_rows(db, s.id)
            deleted += 1

    if deleted:
        await db.commit()
    logger.info("Retention purge (days=%s): deleted %d session(s)", retention_days, deleted)
    return RetentionPurgeResult(
        retention_days=retention_days,
        deleted_sessions=deleted,
        cutoff=cutoff.isoformat(),
    )


@router.get("/{session_id}", response_model=HistorySessionDetail)
async def get_history_detail(session_id: str, db: AsyncSession = Depends(get_session)):
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return await _build_session_detail(db, session)


@router.get("/{session_id}/export")
async def export_session_notes(
    session_id: str,
    format: str = Query(default="markdown", pattern="^(markdown|json)$"),
    db: AsyncSession = Depends(get_session),
):
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    detail = await _build_session_detail(db, session)
    safe_slug = "".join(c if c.isalnum() else "_" for c in session.title)[:50].strip("_") or "session"

    if format == "json":
        return Response(
            content=detail.model_dump_json(indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{safe_slug}.json"'},
        )

    lines = [
        f"# Interview Notes — {detail.session.title}",
        "",
        f"- **Type:** {detail.session.type}",
        f"- **Status:** {detail.session.status}",
        f"- **Date:** {detail.session.created_at.isoformat()}",
        f"- **Duration:** {detail.session.duration_seconds or 0} seconds",
        "",
        "---",
        "",
        "## Questions & Suggested Answers",
        "",
    ]
    if not detail.qa_pairs:
        lines.append("*(No questions recorded in this session.)*")
    else:
        for idx, qa in enumerate(detail.qa_pairs, 1):
            lines.append(f"### Q{idx} ({qa.question_type}): {qa.question_text}")
            lines.append("")
            if not qa.answers:
                lines.append("*(No answer generated.)*")
            else:
                latest = qa.answers[-1]
                lines.append(f"**Answer ({latest['style']} — {latest['model_used']}):**")
                lines.append("")
                lines.append(latest["answer_text"])
            lines.append("")

    lines.extend(["---", "", "## Full Transcript", ""])
    if not detail.transcript:
        lines.append("*(No transcript segments recorded.)*")
    else:
        for seg in detail.transcript:
            lines.append(f"- **[{seg['timestamp']}] {seg['speaker_label']}:** {seg['text']}")

    md_content = "\n".join(lines) + "\n"
    return Response(
        content=md_content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe_slug}.md"'},
    )


@router.delete("/{session_id}/transcript", status_code=status.HTTP_204_NO_CONTENT)
async def purge_session_transcript_only(session_id: str, db: AsyncSession = Depends(get_session)):
    """User-controlled transcript deletion while retaining session metadata and Q&A notes."""
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    t_res = await db.execute(
        select(TranscriptSegment).where(TranscriptSegment.session_id == session_id)
    )
    for ts in t_res.scalars().all():
        await db.delete(ts)
    await db.commit()


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_history_session(session_id: str, db: AsyncSession = Depends(get_session)):
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    await cascade_delete_session_rows(db, session_id)
    await db.commit()
