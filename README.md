# Interview Copilot AI

A personal, single-user, local-first real-time AI interview assistant. Captures permitted interview audio, transcribes speech in real time, detects interview questions, retrieves facts from your uploaded resume and personal knowledge base, and streams grounded AI-suggested answers to a live workspace.

> **For personal interview preparation and live interviews where AI assistance is explicitly permitted.** No covert recording, hidden capture, screen-share evasion, or proctoring bypass is implemented.

---

## End-to-End Pipeline

```
Browser Audio (Mic 0x01 + Shared Tab 0x02, 16kHz 16-bit PCM)
  └─▶ WebSocket /ws/audio/{session_id}
        └─▶ SpeechToTextProvider (faster-whisper local | Deepgram cloud)
              └─▶ TranscriptManager (VAD silence gate · partial/final · dedupe · SQLite)
                    └─▶ QuestionDetectionEngine (direct · indirect · technical · follow-up · fragment merge)
                          └─▶ ContextManager (transcript window · prior Q&A · Resume · BM25 KB)
                                └─▶ AnswerGenerationService (Gemini | OpenAI · 4 styles · streaming)
                                      └─▶ WebSocket /ws/session/{session_id} ─▶ Live Workspace UI
```

Full architecture: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

---

## Implemented Modules (Phases 0–9 Complete)

| Module | Route / Endpoint | Status |
|--------|------------------|--------|
| **Main Dashboard & Session Management** | `/`, `/session/new`, `/api/sessions/*` | ✅ Complete |
| **Live Interview Workspace** | `/session/[id]`, `/ws/audio/{id}`, `/ws/session/{id}` | ✅ Complete |
| **Audio Capture Engine & Diagnostics** | `/audio-test`, `AudioCaptureProvider` | ✅ Complete |
| **Streaming Speech-to-Text** | `WhisperProvider` (local), `DeepgramProvider` | ✅ Complete |
| **Question Detection Engine** | `QuestionDetectionEngine`, `POST /api/sessions/{id}/questions` | ✅ Complete |
| **AI Answer Generation (4 Styles + Expand)** | `GeminiProvider`, `OpenAIProvider`, `AnswerGenerationService` | ✅ Complete |
| **Permitted Screen Reader & Auto-Watch** | `POST /api/sessions/{id}/analyze-screen`, `ScreenCaptureProvider`, `ScreenAnalyzerService` | ✅ Complete |
| **Structured Gemini Coaching & Few-Shot Profile** | `/settings`, `ContextManager`, `StructuredAnswerView` | ✅ Complete |
| **Resume Management (PDF/DOCX)** | `/resume`, `/api/resume/*` | ✅ Complete |
| **Personal Knowledge Base (17 Categories, BM25)** | `/knowledge-base`, `/api/knowledge-base/*` | ✅ Complete |
| **Interview History, Search, Export & Retention** | `/history`, `/api/history/*` | ✅ Complete |
| **Mock Interview Mode (Isolated Data Path)** | `/mock`, `/api/mock/*` | ✅ Complete |
| **Settings & Configuration** | `/settings`, `/api/settings/*` | ✅ Complete |
| **Windows Desktop Companion (Zoom/Teams WASAPI)** | `desktop_companion/wasapi_bridge.py`, `docs/DESKTOP_COMPANION.md` | ✅ PoC Complete |

---

## Prerequisites

| Tool | Minimum Version | Tested Version |
|------|----------------|----------------|
| Node.js | 18+ | v24.22.1 |
| npm | 9+ | 11.19.1 |
| Python | 3.11+ | 3.14.7 |
| Browser | Chrome or Edge (for tab audio) | Chromium desktop |

> **Note on `ffmpeg`:** Not required for live browser streaming — `AudioCaptureProvider` resamples directly to 16kHz 16-bit mono PCM in the browser and `WhisperProvider` decodes directly via `numpy` (see `DECISIONS.md` D008).

---

## Quick Start

### 1. Configure Environment Variables

```powershell
copy .env.example .env
```

Edit `.env` and add **at least one LLM API key** (never commit `.env`):

| Key | Provider | Cost | Get Key |
|-----|----------|------|---------|
| `GOOGLE_API_KEY` *(recommended)* | Google Gemini 2.0 Flash | Free tier (15 req/min) | https://aistudio.google.com |
| `OPENAI_API_KEY` *(optional)* | OpenAI GPT-4o-mini | Pay-as-you-go | https://platform.openai.com |
| `DEEPGRAM_API_KEY` *(optional)* | Deepgram Nova-2 STT | Verify current pricing | https://deepgram.com |

Local `faster-whisper` is used by default for speech-to-text (\$0 cost, no key needed).

### 2. Automated Setup (Windows PowerShell)

```powershell
.\scripts\setup.ps1
.\scripts\dev.ps1
```

### 3. Manual Startup

**Backend (port 8000):**
```powershell
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```
- Health check: http://localhost:8000/health
- Swagger API docs: http://localhost:8000/docs

**Frontend (port 3000):**
```powershell
cd frontend
npm install
npm run dev
```
- Web app: http://localhost:3000

---

## Running Tests & Verification

```powershell
# Backend test suite (unit + integration + WebSocket + real Whisper WAV + full pipeline + QA hardening)
cd backend
python -m pytest tests/ -v

# Frontend lint & production build
cd frontend
npm run lint
npm run build
```

Latest verified results (2026-11-18):
- **Backend `pytest`:** 68 passed / 0 failed
- **Frontend `npm run lint`:** 0 errors, 0 warnings
- **Frontend `npm run build`:** 12/12 routes compiled cleanly
- **Live Full-Stack Smoke Check:** 16/16 backend endpoints & frontend pages HTTP 200 OK

---

## Measured Performance (`docs/PERF.md`)

- **Local Whisper (`tiny`, int8 CPU, 3.4s spoken WAV):** `312 ms` warm inference (`~912 ms` with 600ms silence gate)
- **Question Detection Engine (19-turn labeled set):** `0.281 ms` avg (`1.00` Precision / `1.00` Recall / `1.00` F1)
- **Context Assembly + WS Dispatch Overhead:** `~3 ms`
- **Live Cloud LLM TTFT & Total Latency:** Automatically recorded per answer in `ttft_ms` and `generation_time_ms` once `GOOGLE_API_KEY` or `OPENAI_API_KEY` is configured.

---

## Security, Privacy & Known Limitations

- All data (SQLite DB, resumes, KB uploads, transcripts) stays strictly local under `storage/` (gitignored).
- File uploads enforce extension, MIME, magic-byte, size, path-traversal, DOCX macro/XXE, and malformed PDF validation.
- Structured backend logs automatically redact API key patterns (`sk-...`, `AIza...`, `api_key=...`).
- Browser audio capture is explicitly permission-based with live VU level meters at all times.
- See [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md) for full details on Zoom/Teams desktop audio limits, macOS/Firefox constraints, and best-effort speaker labels.
