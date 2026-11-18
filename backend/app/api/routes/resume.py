"""
Resume Management API — upload, text extraction, structured fields, preview, replace, delete.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.database.connection import get_session
from app.models.resume import Resume
from app.services.knowledge_base.parser import (
    MAX_RESUME_BYTES,
    RESUME_EXTENSIONS,
    delete_file_safely,
    extract_document_text,
    save_file_safely,
    validate_upload,
)
from app.services.knowledge_base.resume_extractor import extract_resume_fields

logger = logging.getLogger(__name__)
router = APIRouter()


class ResumeDetail(BaseModel):
    id: str
    filename: str
    uploaded_at: datetime
    extracted_text: str
    skills: List[str]
    experience: List[str]
    projects: List[str]
    education: List[str]
    certifications: List[str]
    is_active: bool


class ActiveResumeResponse(BaseModel):
    has_resume: bool
    resume: Optional[ResumeDetail] = None


def _row_to_detail(row: Resume) -> ResumeDetail:
    def _load(raw: Optional[str]) -> List[str]:
        if not raw:
            return []
        try:
            data = json.loads(raw)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    return ResumeDetail(
        id=row.id,
        filename=row.filename,
        uploaded_at=row.uploaded_at,
        extracted_text=row.extracted_text or "",
        skills=_load(row.skills),
        experience=_load(row.experience),
        projects=_load(row.projects),
        education=_load(row.education),
        certifications=_load(row.certifications),
        is_active=row.is_active,
    )


@router.get("/", response_model=ActiveResumeResponse)
async def get_active_resume(db: AsyncSession = Depends(get_session)):
    res = await db.execute(
        select(Resume)
        .where(Resume.is_active == True)  # noqa: E712
        .order_by(Resume.uploaded_at.desc())
        .limit(1)
    )
    row = res.scalar_one_or_none()
    if row is None:
        return ActiveResumeResponse(has_resume=False, resume=None)
    return ActiveResumeResponse(has_resume=True, resume=_row_to_detail(row))


@router.post("/upload", response_model=ResumeDetail, status_code=status.HTTP_201_CREATED)
async def upload_or_replace_resume(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_session),
):
    """Upload a PDF or DOCX resume, replacing any previously active resume."""
    data = await file.read()
    try:
        safe_name, ext = validate_upload(
            filename=file.filename or "",
            content_type=file.content_type,
            data=data,
            allowed_extensions=RESUME_EXTENSIONS,
            max_bytes=MAX_RESUME_BYTES,
        )
        extracted_text = extract_document_text(ext, data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": exc.code, "message": exc.message},
        ) from exc

    fields = extract_resume_fields(extracted_text)

    storage_dir = Path(settings.storage_path) / "resumes"
    saved_path = save_file_safely(storage_dir, safe_name, data)

    # Remove any prior active resume cleanly (file + DB row) so replacement leaves no orphans
    prev_res = await db.execute(select(Resume).where(Resume.is_active == True))  # noqa: E712
    for prev in prev_res.scalars().all():
        delete_file_safely(prev.file_path)
        await db.delete(prev)

    row = Resume(
        filename=safe_name,
        file_path=str(saved_path),
        extracted_text=extracted_text,
        skills=json.dumps(fields["skills"]),
        experience=json.dumps(fields["experience"]),
        projects=json.dumps(fields["projects"]),
        education=json.dumps(fields["education"]),
        certifications=json.dumps(fields["certifications"]),
        is_active=True,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    logger.info(
        "Resume uploaded: id=%s file=%s skills=%d projects=%d",
        row.id,
        safe_name,
        len(fields["skills"]),
        len(fields["projects"]),
    )
    return _row_to_detail(row)


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume_by_id(resume_id: str, db: AsyncSession = Depends(get_session)):
    row = await db.get(Resume, resume_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Resume '{resume_id}' not found")
    delete_file_safely(row.file_path)
    await db.delete(row)
    await db.commit()
    logger.info("Resume deleted: %s", resume_id)


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_active_resume(db: AsyncSession = Depends(get_session)):
    res = await db.execute(select(Resume).where(Resume.is_active == True))  # noqa: E712
    rows = res.scalars().all()
    for row in rows:
        delete_file_safely(row.file_path)
        await db.delete(row)
    await db.commit()
