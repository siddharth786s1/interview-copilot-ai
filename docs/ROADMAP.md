# Development Roadmap — Interview Copilot AI

Last updated: 2026-11-18

---

## Phase Summary

| Phase | Name | Priority | DoD Status |
|-------|------|----------|------------|
| 0 | Environment + Planning | ✅ Complete | Awaiting approval |
| 1 | Foundation | 🔲 Pending | — |
| 2 | Dashboard + Session CRUD | 🔲 Pending | — |
| 3 | Audio Capture Prototype | 🔲 Pending | — |
| 4 | Streaming Transcription | 🔲 Pending | — |
| 5 | Question Detection | 🔲 Pending | — |
| 6 | AI Answer Generation | 🔲 Pending | — |
| 7 | Resume + Knowledge Base | 🔲 Pending | — |
| 8 | History + Mock Mode | 🔲 Pending | — |
| 9 | QA Hardening | 🔲 Pending | — |
| 10 | Desktop Companion (optional) | 🔲 Pending | — |

---

## PHASE 0 — Environment + Planning

**Goal:** Full environment survey, architecture, and planning documents.

**Definition of Done:**
- [x] Environment versions recorded in `docs/ENVIRONMENT.md`
- [x] `docs/ARCHITECTURE.md` — full component diagram + DB schema + WS contract
- [x] `docs/ROADMAP.md` — this file
- [x] `docs/RISKS.md` — audio limits, latency, provider, cost risks
- [x] `docs/API_KEYS.md` — required accounts, costs, free alternatives
- [x] `docs/COSTS.md` — per-session and monthly cost estimates
- [x] `PROGRESS.md`, `DECISIONS.md`, `KNOWN_ISSUES.md` initialized
- [x] **STOP — wait for human approval before Phase 1**

---

## PHASE 1 — Project Foundation

**Goal:** Running skeleton: Next.js + FastAPI + SQLite + health check.

**Deliverables:**
- Monorepo structure created
- Next.js 15 initialized with TypeScript + Tailwind + shadcn/ui
- FastAPI backend initialized with uvicorn
- `/health` GET endpoint returns `{"status": "ok", "version": "0.1.0"}`
- SQLite DB + all table definitions via SQLModel
- Database init script creates all tables on startup
- `.env.example` with all required variables documented
- `README.md` with exact run commands
- `pytest` test suite exists and passes (empty is OK)
- `npm run lint` passes
- Both servers start without errors

**Definition of Done:** `GET /health` → 200, `npm run dev` renders Next.js, `pytest` green.

**Key decisions (see DECISIONS.md):**
- Python package manager: `pip` with `requirements.txt` (uv available as alternative)
- Next.js: App Router
- DB: SQLite for local dev, repository pattern for PostgreSQL compatibility

---

## PHASE 2 — Dashboard + Session CRUD

**Goal:** Full dashboard UI + session create/list/open/delete via real API.

**Deliverables:**
- Dashboard with all nav links (all pages exist, even if placeholder)
- Session creation modal: title, type, audio source selection
- Session list page
- Session detail page (workspace shell)
- Session delete
- Settings page (persists to DB)
- Frontend ↔ backend integration tests for each operation
- No dead nav links

**Definition of Done:** All 5 session operations work end-to-end via real API calls.

---

## PHASE 3 — Audio Capture Prototype

**Goal:** Working browser audio capture with visible status and error handling.

**Deliverables:**
- `AudioCaptureProvider` interface + browser implementation
- Microphone capture (`getUserMedia`) — independent
- Tab/system capture (`getDisplayMedia` + audio track) — independent
- Independent device selection for each source
- Permission denied → visible error message
- Track ended event → visible reconnect UI
- Device unplug → graceful handler
- Audio level visualizer (input meter) for each source
- Manual QA recorded in `docs/AUDIO_QA.md` (Chrome + 1 other browser)

**Definition of Done:** Loopback test page shows live input levels for mic and tab audio separately.

> If tab audio unavailable in test environment: document it, proceed mic-only.

---

## PHASE 4 — Streaming Transcription

**Goal:** Real audio → real transcript text displayed in browser over WebSocket.

**Deliverables:**
- `SpeechToTextProvider` ABC in Python
- `WhisperProvider` using faster-whisper (chunked processing)
- Audio WebSocket endpoint (`/ws/audio/{session_id}`)
- Session WebSocket endpoint (`/ws/session/{session_id}`)
- Partial + final transcript segments rendered distinctly in UI
- Timestamps on each segment
- Duplicate suppression (hash-based)
- Reconnect logic tested (kill socket → auto-reconnect)
- Latency measured (audio → displayed text) → `docs/PERF.md`
- Language configurable via settings

**Definition of Done:** Speaking into mic → text appears in browser within reasonable latency; duplicate suppression test passes.

---

## PHASE 5 — Question Detection Engine

**Goal:** Automatic detection of interview questions from transcript stream.

**Deliverables:**
- `QuestionDetectionEngine` with unit tests
- Detects: direct questions, indirect questions, technical questions, follow-ups
- Duplicate suppression (same question not sent twice)
- Multi-segment question merging (question that spans multiple transcript segments)
- Small talk / non-question suppression
- Manual question input UI (always available as fallback)
- Unit tests over all 7 required test questions + negative cases
- Precision/recall recorded in `docs/QUESTION_DETECTION.md`

**Definition of Done:** All 7 test questions detected; small talk suppressed; duplicates suppressed; manual input wired.

---

## PHASE 6 — AI Answer Generation

**Goal:** Detected question → streaming AI answer displayed in browser.

**Deliverables:**
- `LLMProvider` ABC
- `GeminiProvider` (Google Gemini 2.0 Flash — free tier)
- `OpenAIProvider` (GPT-4o-mini — optional)
- `AnswerGenerationService` wiring context + provider
- `ContextManager`: sliding window transcript + last 5 Q&A + resume facts + KB top-3
- All 4 answer styles: SHORT, DETAILED, PRACTICAL, STEP-BY-STEP
- Style selectable from live dashboard
- Streaming display (tokens appear as generated)
- Timeout (30s) + retry (1 attempt) + cancellation on session end
- Grounding guard: will not invent experience not in resume
- Latency measured → `docs/PERF.md`
- Error paths: LLM 429, 500, timeout — all handled gracefully with visible message

**Definition of Done:** End-to-end: detected question → streaming answer appears in dashboard; all 4 styles work; grounding guard tested.

---

## PHASE 7 — Resume + Knowledge Base

**Goal:** Upload personal documents; retrieval improves answer quality.

**Deliverables:**
- Resume upload: PDF + DOCX
- Text extraction (pypdf + python-docx)
- Structured extraction: skills, experience, education, certs, projects (via LLM)
- Resume preview, replace, delete
- KB document upload: PDF, DOCX, TXT, MD
- KB categories (all 17 required categories)
- BM25 keyword retrieval
- Retrieval results injected into ContextManager
- Demonstrable answer quality improvement on scripted test
- Malicious-file rejection tests: oversized, wrong MIME, malformed PDF

**Definition of Done:** Upload → extract → retrieve → improved answer quality verified by test.

---

## PHASE 8 — History + Mock Interview Mode

**Goal:** Persistent session history + independent mock interview flow.

**Deliverables:**
- Full session persistence (title, date, type, transcript, questions, answers, duration)
- History list / open / search / delete / export (JSON + text)
- Retention settings actually delete data
- Mock interview: topic → question → answer → evaluate → feedback → suggest
- Mock uses a **separate** DB table path from live sessions (enforced by test)
- Performance tracking across mock sessions (score trend)

**Definition of Done:** History CRUD + export work; mock mode full loop works; schema separation enforced by test.

---

## PHASE 9 — QA Hardening

**Goal:** Full test suite green; all failure scenarios handled; docs complete.

**Deliverables:**
- Full backend test suite: unit + integration + pipeline
- All 7 required test questions pass through full pipeline (mocked STT/LLM)
- Failure injection: API 500, timeout, socket drop, mic unplug — all handled
- Zero console errors on happy path
- `docs/KNOWN_LIMITATIONS.md` written honestly
- `README.md` complete with setup, run, test instructions
- Latency summary in `docs/PERF.md`

**Definition of Done:** `pytest` all green; `npm run lint` clean; manual happy-path walkthrough with no errors.

---

## PHASE 10 — Windows Desktop Companion (optional, requires explicit request)

**Goal:** Evaluate and prototype native system-audio capture for Zoom/Teams.

**Deliverables:**
- Tauri vs Electron comparison document
- Minimal Windows WASAPI loopback audio capture PoC
- PoC connects to existing FastAPI backend (no rewrite)
- Existing test suite still passes after PoC integration

**Definition of Done:** PoC captures Zoom/Teams audio → sends to backend → transcript appears. No existing services rewritten.

---

## First Milestone (Phase 1 Target)

By end of Phase 1, you will have:
1. `cd frontend && npm run dev` → Next.js dashboard loads at http://localhost:3000
2. `cd backend && uvicorn app.main:app --reload` → FastAPI at http://localhost:8000
3. `GET http://localhost:8000/health` → `{"status": "ok", "version": "0.1.0"}`
4. `GET http://localhost:8000/docs` → Swagger UI with all planned endpoints listed
5. SQLite database created at `./storage/interview_copilot.db`
6. `cd backend && pytest` → passes (empty suite)
7. `cd frontend && npm run lint` → no errors
