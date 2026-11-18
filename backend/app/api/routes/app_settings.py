"""
App Settings API — get and update settings (persisted to DB single row),
including Gemini structured answer formatting and few-shot coaching examples.
"""
import json
import logging
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.database.connection import get_session
from app.models.settings import AppSettings
from app.schemas.settings import FewShotExample, SettingsResponse, SettingsUpdate

logger = logging.getLogger(__name__)
router = APIRouter()


def _parse_examples(raw: str | None) -> List[FewShotExample]:
    if not raw:
        return []
    try:
        items = json.loads(raw)
        if not isinstance(items, list):
            return []
        return [FewShotExample(**item) for item in items if isinstance(item, dict)]
    except Exception:
        return []


def _to_response(row: AppSettings) -> SettingsResponse:
    return SettingsResponse(
        id=row.id,
        stt_provider=row.stt_provider,
        llm_provider=row.llm_provider,
        llm_model=row.llm_model,
        whisper_model_size=row.whisper_model_size,
        language=row.language,
        default_answer_style=row.default_answer_style,
        default_technical_depth=row.default_technical_depth,
        theme=row.theme,
        retention_days=row.retention_days,
        structured_output=row.structured_output,
        target_role=row.target_role or "",
        custom_instructions=row.custom_instructions or "",
        few_shot_examples=_parse_examples(row.few_shot_examples),
        updated_at=row.updated_at,
    )


async def _get_or_create_settings(db: AsyncSession) -> AppSettings:
    result = await db.execute(select(AppSettings).where(AppSettings.id == 1))
    settings_row = result.scalar_one_or_none()
    if settings_row is None:
        settings_row = AppSettings()
        db.add(settings_row)
        await db.commit()
        await db.refresh(settings_row)
    return settings_row


@router.get("/", response_model=SettingsResponse)
async def get_settings(db: AsyncSession = Depends(get_session)):
    row = await _get_or_create_settings(db)
    return _to_response(row)


@router.patch("/", response_model=SettingsResponse)
async def update_settings(payload: SettingsUpdate, db: AsyncSession = Depends(get_session)):
    settings_row = await _get_or_create_settings(db)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "few_shot_examples":
            serialized = json.dumps([ex if isinstance(ex, dict) else ex.model_dump() for ex in (value or [])])
            settings_row.few_shot_examples = serialized
        else:
            setattr(settings_row, field, value)
    settings_row.updated_at = datetime.now(timezone.utc)
    db.add(settings_row)
    await db.commit()
    await db.refresh(settings_row)
    logger.info("Settings updated: %s", list(update_data.keys()))
    return _to_response(settings_row)
