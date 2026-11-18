"""
Personal Knowledge Base API — upload (PDF/DOCX/TXT/MD), 17 categories,
chunking, BM25 keyword retrieval, preview, and deletion.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.database.connection import get_session
from app.models.knowledge_base import KBDocument
from app.services.knowledge_base.chunker import KB_CATEGORIES, chunk_text
from app.services.knowledge_base.parser import (
    KB_EXTENSIONS,
    MAX_KB_BYTES,
    delete_file_safely,
    extract_document_text,
    save_file_safely,
    validate_upload,
)
from app.services.knowledge_base.retriever import retrieve_from_db

logger = logging.getLogger(__name__)
router = APIRouter()


class KBDocumentSummary(BaseModel):
    id: str
    filename: str
    category: str
    uploaded_at: datetime
    chunk_count: int
    char_count: int
    preview: str


class KBDocumentDetail(KBDocumentSummary):
    extracted_text: str


class KBSearchResult(BaseModel):
    document_id: str
    filename: str
    category: str
    excerpt: str
    score: float


def _to_summary(row: KBDocument) -> KBDocumentSummary:
    text = row.extracted_text or ""
    chunk_count = 0
    if row.chunks:
        try:
            chunk_count = len(json.loads(row.chunks))
        except Exception:
            chunk_count = 0
    return KBDocumentSummary(
        id=row.id,
        filename=row.filename,
        category=row.category,
        uploaded_at=row.uploaded_at,
        chunk_count=chunk_count,
        char_count=len(text),
        preview=text[:240],
    )


@router.get("/categories", response_model=List[str])
async def list_categories():
    return KB_CATEGORIES


@router.get("/search", response_model=List[KBSearchResult])
async def search_knowledge_base(
    q: str = Query(..., min_length=1, max_length=500),
    top_k: int = Query(default=5, ge=1, le=20),
    category: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_session),
):
    hits = await retrieve_from_db(db=db, query=q, top_k=top_k, category=category)
    return [KBSearchResult(**hit) for hit in hits]


@router.get("/", response_model=List[KBDocumentSummary])
async def list_kb_documents(
    category: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_session),
):
    stmt = select(KBDocument).where(KBDocument.is_active == True)  # noqa: E712
    if category and category.lower() != "all":
        stmt = stmt.where(KBDocument.category == category)
    stmt = stmt.order_by(KBDocument.uploaded_at.desc())
    res = await db.execute(stmt)
    return [_to_summary(r) for r in res.scalars().all()]


@router.get("/{doc_id}", response_model=KBDocumentDetail)
async def get_kb_document(doc_id: str, db: AsyncSession = Depends(get_session)):
    row = await db.get(KBDocument, doc_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")
    summary = _to_summary(row)
    return KBDocumentDetail(**summary.model_dump(), extracted_text=row.extracted_text or "")


@router.post("/upload", response_model=KBDocumentSummary, status_code=status.HTTP_201_CREATED)
async def upload_kb_document(
    file: UploadFile = File(...),
    category: str = Form(default="Custom Topics"),
    db: AsyncSession = Depends(get_session),
):
    resolved_category = category.strip() if category and category.strip() in KB_CATEGORIES else "Custom Topics"
    data = await file.read()

    try:
        safe_name, ext = validate_upload(
            filename=file.filename or "",
            content_type=file.content_type,
            data=data,
            allowed_extensions=KB_EXTENSIONS,
            max_bytes=MAX_KB_BYTES,
        )
        extracted_text = extract_document_text(ext, data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": exc.code, "message": exc.message},
        ) from exc

    chunks = chunk_text(extracted_text)
    storage_dir = Path(settings.storage_path) / "uploads"
    saved_path = save_file_safely(storage_dir, safe_name, data)

    row = KBDocument(
        filename=safe_name,
        file_path=str(saved_path),
        category=resolved_category,
        extracted_text=extracted_text,
        chunks=json.dumps(chunks),
        is_active=True,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    logger.info(
        "KB document uploaded: id=%s file=%s category=%s chunks=%d",
        row.id,
        safe_name,
        resolved_category,
        len(chunks),
    )
    return _to_summary(row)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_kb_document(doc_id: str, db: AsyncSession = Depends(get_session)):
    row = await db.get(KBDocument, doc_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")
    delete_file_safely(row.file_path)
    await db.delete(row)
    await db.commit()
    logger.info("KB document deleted: %s", doc_id)
