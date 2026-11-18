"""
Interview Copilot AI — FastAPI application entry point.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.database.connection import init_db
from app.api.routes import health, sessions, resume, knowledge_base, history, mock_interview, app_settings
from app.api.websockets import audio_ws, session_ws


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    setup_logging()
    await init_db()
    yield
    # Shutdown: clean up resources if needed


app = FastAPI(
    title="Interview Copilot AI",
    description="Personal real-time AI interview assistant",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response

# REST routes
app.include_router(health.router, tags=["health"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(resume.router, prefix="/api/resume", tags=["resume"])
app.include_router(knowledge_base.router, prefix="/api/knowledge-base", tags=["knowledge-base"])
app.include_router(history.router, prefix="/api/history", tags=["history"])
app.include_router(mock_interview.router, prefix="/api/mock", tags=["mock-interview"])
app.include_router(app_settings.router, prefix="/api/settings", tags=["settings"])

# WebSocket routes
app.include_router(audio_ws.router)
app.include_router(session_ws.router)
