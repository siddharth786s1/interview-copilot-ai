# Decisions Log — Interview Copilot AI

---

## 2026-11-18 — D001: Python Package Manager

**Decision:** Use `pip` with `requirements.txt` for backend dependencies.

**Rationale:** `uv` is available and faster, but `pip` + `requirements.txt` is universally understood and requires no extra tooling for contributors. `uv` can be adopted later for speed improvements.

**Alternatives considered:**
- `uv` with `pyproject.toml` — more modern but adds a learning curve for setup docs
- `poetry` — not installed in environment

---

## 2026-11-18 — D002: STT Primary Provider

**Decision:** Default to `faster-whisper` (local) as primary STT provider; `DeepgramProvider` as optional cloud provider.

**Rationale:** 
- faster-whisper 1.2.1 is already installed and working.
- Zero cost for local use.
- Deepgram available as a drop-in upgrade when lower latency is required.
- Provider interface means switching requires only a config change.

**Alternatives considered:**
- Deepgram as default — better latency but requires API key and ongoing cost verification
- OpenAI Whisper API — no streaming, \$0.006/min

---

## 2026-11-18 — D003: LLM Primary Provider

**Decision:** Default to Google Gemini 2.0 Flash (`google-genai` SDK).

**Rationale:**
- `google-genai` 3.4.0 already installed.
- Gemini 2.0 Flash has a free tier (15 req/min, 1500 req/day) — covers personal interview use.
- OpenAI GPT-4o-mini available as alternative via config.

**Alternatives considered:**
- OpenAI GPT-4o-mini — better-known but costs ~\$0.60/1M tokens
- Local Llama via Ollama — highest privacy, highest hardware requirement, lowest quality

---

## 2026-11-18 — D004: ORM Layer

**Decision:** Use `SQLModel` (which wraps SQLAlchemy) for the ORM layer.

**Rationale:**
- SQLAlchemy 2.1.9 already installed (SQLModel's dependency).
- SQLModel provides Pydantic v2-compatible models + table definitions in one class.
- Repository pattern isolates the ORM so PostgreSQL can drop in without changing service code.

**Alternatives considered:**
- Raw SQLAlchemy — more verbose, no Pydantic integration out of the box
- Tortoise ORM — not pre-installed; different async pattern

---

## 2026-11-18 — D005: Next.js Router

**Decision:** Use Next.js App Router (not Pages Router).

**Rationale:** App Router is the current Next.js standard (Next.js 15). Server Components available for static pages. `use client` for interactive components.

---

## 2026-11-18 — D006: Knowledge Base Retrieval

**Decision:** Start with BM25 keyword retrieval (`rank-bm25` package); add vector search only if KB exceeds ~100 documents or retrieval quality is demonstrably poor.

**Rationale:** BM25 is fast, deterministic, requires no embedding API calls, and works well for < 100 documents. YAGNI — do not add vector DBs until justified.

**Alternatives considered:**
- ChromaDB with sentence-transformers — better semantic match, \$0 local, but heavy dependency
- Pinecone / Weaviate — cloud, overkill for personal use

---

## 2026-11-18 — D007: Audio Format for Whisper

**Decision:** Resample all browser audio (WebM/Opus or PCM) to 16kHz 16-bit mono WAV on the backend before passing to faster-whisper.

**Rationale:** faster-whisper requires specific audio format. ffmpeg (once installed) handles arbitrary browser codec output. If ffmpeg unavailable, require PCM from browser directly.

**Risk:** ffmpeg not currently installed — noted in KNOWN_ISSUES.md, Phase 1 setup script will document installation.

---

## 2026-11-18 — D008: Direct 16kHz PCM Streaming (Eliminates ffmpeg Dependency for Live Audio)

**Decision:** Resample audio to 16kHz 16-bit mono linear PCM in the browser (`AudioCaptureProvider`) and convert directly to `numpy.float32` in `WhisperProvider`, bypassing `ffmpeg` completely for live streaming.

**Rationale:**
- `ffmpeg` is not installed on the Windows host (`KI-001`).
- `faster-whisper` natively accepts a 16kHz `numpy.float32` waveform array.
- Direct binary PCM avoids codec encode/decode latency (~0ms decode overhead; verified 312ms warm Whisper inference).
- Prepends a 1-byte source header (`0x01`=mic, `0x02`=tab) so speaker streams remain separated end-to-end.

**Alternatives considered:**
- Sending MediaRecorder WebM/Opus chunks and decoding via ffmpeg subprocess — adds external binary dependency and transcoding latency.

---

## 2026-11-18 — D009: Persist Finalized Transcript Segments Before WebSocket Broadcast

**Decision:** In `SessionConnectionManager`, write finalized `TranscriptSegment` rows to SQLite before broadcasting the `is_final: true` WebSocket event (partial segments broadcast immediately without DB writes).

**Rationale:**
- Local SQLite insert takes < 1ms.
- Guarantees that by the time the frontend receives a finalized segment, a page refresh or immediate socket disconnect cannot lose it (caught and verified by `test_ws_audio_to_transcript_and_db_persistence`).

---

## 2026-11-18 — D010: Windows Desktop Companion Architecture (Python WASAPI Bridge PoC; Tauri v2 for Future Packaging)

**Decision:** Implement Phase 10's Zoom/Teams desktop audio PoC as a lightweight Python Windows WASAPI loopback bridge (`desktop_companion/wasapi_bridge.py` using `soundcard`) streaming directly to the existing `/ws/audio/{session_id}` WebSocket with zero backend rewrites. Recommend **Tauri v2** (over Electron) if a packaged standalone `.exe` is desired later.

**Rationale:**
- Verified live on this Windows host against `Speakers (Realtek(R) Audio)` (`isloopback=True`, 16kHz mono float32 → 16-bit PCM).
- Requires zero extra build toolchains (Rust/MSVC not installed on host) and zero changes to `TranscriptManager`, `QuestionDetectionEngine`, `AnswerGenerationService`, or Next.js UI.
- Full evaluation recorded in `docs/DESKTOP_COMPANION.md`.

---

## 2026-11-18 — D011: Default Gemini Model Upgraded to `gemini-3.5-flash-lite`

**Decision:** Switch default Gemini model from `gemini-2.0-flash` (deprecated 404 on live API) to `gemini-3.5-flash-lite` and raise `AnswerGenerationService` output ceilings to `600` (short) / `1400` (other styles).

**Rationale:**
- Live API verification showed `gemini-2.0-flash` and `gemini-2.5-flash*` return 404.
- `gemini-3.8-flash` defaults to extended thinking (25s TTFT), which is too slow for real-time interviews.
- `gemini-3.5-flash-lite` streamed complete, accurate interview answers in **611–1,465 ms TTFT** and **825–1,628 ms total** with zero truncation and full adherence to the Grounding Guard.
- Users can still select any other Gemini or OpenAI model from Settings.

---

## 2026-11-18 — D012: Permitted Visual Screen Reader & Structured Gemini Coaching Profile

**Decision:** Add an explicit, user-consented browser screen reader (`getDisplayMedia` + visible `Screen Active` badge & live miniature thumbnail preview) paired with multimodal `ScreenAnalyzerService` (`POST /api/sessions/{id}/analyze-screen`) and a persistent Gemini Structured Output & Coaching Profile in `AppSettings`.

**Rationale:**
- Many technical interviews show coding prompts, SQL schemas, error stack traces, or architecture diagrams on screen alongside spoken discussion.
- Explicit `getDisplayMedia` with visible sharing status and thumbnail preview ensures 100% transparent, permitted operation (never covert).
- Lightweight 32×18 client-side pixel diffing (`ScreenCaptureProvider`) avoids redundant LLM calls in Auto-Watch mode when the screen hasn't changed; backend `auto_mode=True` instructs Gemini to return `ACTIONABLE: NO | SUMMARY: ...` on ordinary video-call views while still updating `ws_manager._screen_context` so spoken follow-ups remain screen-aware.
- Structured response headings (`**Direct Answer**`, `**Key Points**`, `**Practical Example**`/`**Quick Tip**`, `**Follow-up Tip**`) plus user-configurable Target Role, Custom Instructions, and Few-Shot Example Q&A pairs train Gemini to output crisp, scannable answers rendered cleanly via `StructuredAnswerView`.
