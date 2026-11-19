"""
Database connection and session factory using async SQLite.
"""
import os
from pathlib import Path
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
import aiosqlite  # noqa: F401 — needed for aiosqlite dialect registration

from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Ensure storage directory exists before engine creation
_db_url = settings.database_url
if _db_url.startswith("sqlite"):
    _db_path = _db_url.replace("sqlite+aiosqlite:///", "")
    if _db_path and not _db_path.startswith(":"):
        Path(_db_path).parent.mkdir(parents=True, exist_ok=True)

# Use StaticPool for SQLite to avoid "database is locked" in tests
engine = create_async_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Create all tables and apply safe additive column migrations on startup."""
    import app.models  # noqa: F401
    from sqlalchemy import text

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        # Safe additive migrations for existing SQLite databases
        cols_res = await conn.execute(text("PRAGMA table_info(app_settings)"))
        existing_cols = {row[1] for row in cols_res.fetchall()}
        additive_columns = [
            ("structured_output", "BOOLEAN NOT NULL DEFAULT 1"),
            ("conversation_mode", "BOOLEAN NOT NULL DEFAULT 1"),
            ("target_role", "VARCHAR NOT NULL DEFAULT ''"),
            ("custom_instructions", "TEXT NOT NULL DEFAULT ''"),
            ("few_shot_examples", "TEXT"),
        ]
        for col_name, col_ddl in additive_columns:
            if col_name not in existing_cols:
                await conn.execute(text(f"ALTER TABLE app_settings ADD COLUMN {col_name} {col_ddl}"))
                logger.info("Migrated app_settings: added column '%s'", col_name)
    logger.info("Database initialized at %s", settings.database_url)


async def get_session():
    """FastAPI dependency — yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
