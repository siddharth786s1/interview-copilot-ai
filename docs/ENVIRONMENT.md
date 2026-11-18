# Environment — Interview Copilot AI

Recorded: 2026-11-18

## Runtime Versions

| Tool | Version | Path |
|------|---------|------|
| Node.js | v24.22.1 | C:\Program Files\nodejs\node.exe |
| npm | 11.19.1 | C:\Program Files\nodejs\npx.cmd |
| Python | 3.14.7 | C:\Users\siddh\AppData\Local\Python\pythoncore-3.14-64\python.exe |
| Git | 2.56.0.windows.3 | C:\Program Files\Git\cmd\git.exe |
| uv | 0.12.11 | (available in PATH) |
| ffmpeg | ❌ NOT INSTALLED | must install for audio format conversion |
| pip | 26.2.1 | bundled with Python |

## Pre-installed Python Packages (relevant)

| Package | Version | Notes |
|---------|---------|-------|
| fastapi | 0.163.1 | ✅ Modern FastAPI |
| uvicorn | 0.54.0 | ✅ ASGI server |
| pydantic | 2.14.3 | ✅ v2 |
| SQLAlchemy | 2.1.9 | ✅ Modern |
| openai | 3.52.0 | ✅ Latest SDK (AsyncOpenAI available) |
| google-genai | 3.4.0 | ✅ Gemini SDK |
| faster-whisper | 1.2.1 | ✅ Local Whisper model |
| websockets | 17.4 | ✅ |
| aiofiles | 25.1.0 | ✅ |
| sentencex | 1.0.34 | ✅ Sentence boundary detection |
| google-auth | 2.62.2 | ✅ |

## Missing Python Packages (to install in Phase 1)

| Package | Purpose |
|---------|---------|
| sqlmodel | SQLModel ORM (layered on SQLAlchemy) |
| python-multipart | FastAPI file upload support |
| pypdf | PDF text extraction |
| python-docx | DOCX extraction |
| aiohttp | async HTTP client |
| rank-bm25 | Keyword retrieval for KB |
| httpx | test client for FastAPI |
| pytest | test runner |
| pytest-asyncio | async test support |
| python-jose | JWT (optional, settings auth) |
| python-dotenv | .env loading |

## Missing Tools

| Tool | Action Required |
|------|----------------|
| ffmpeg | Install via `winget install ffmpeg` or Chocolatey — needed for audio resampling |

## OS

- Windows (confirmed by shell environment)
- Browser target: Chrome / Edge (Chromium-based, best getDisplayMedia support)

## Notes

- OpenAI SDK v3.52.0 is the **modern** SDK (`AsyncOpenAI` confirmed available).
- Python 3.14.7 is a very recent release. Confirm all packages work (some may need 3.11-compatible wrappers).
- No sqlmodel pre-installed — will install in Phase 1.
- faster-whisper 1.2.1 supports `WhisperModel` with CTranslate2 backend — suitable for local STT.
