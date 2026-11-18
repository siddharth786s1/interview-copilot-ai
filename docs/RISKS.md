# Risk Register — Interview Copilot AI

Last updated: 2026-11-18

## R1 — Browser Audio Capture (HIGH)

**Risk:** `getDisplayMedia` audio-track support is inconsistent across browsers and platforms.

**Details:**
- Chrome/Edge on Windows: Tab audio via "Share this tab" + "Also share tab audio" ✅ works.
- Chrome on macOS: system-audio capture requires BlackHole or Loopback — browser alone ❌.
- Firefox: `getDisplayMedia` audio track NOT supported by default ❌.
- Safari: Limited support, may require permission entitlements ❌.
- Zoom / Teams desktop apps: **browser APIs cannot capture their audio**. These apps use their own audio mixer and do not route through any browser-capturable stream. The user must use mic-only or manual question input when interviewing in Zoom/Teams desktop.
- Google Meet in browser: Tab audio works if user shares the Meet tab and grants audio ✅.

**Mitigation:** 
- Phase 3 implements capability checks with visible UI messages.
- Route user to manual question input when tab audio unavailable.
- Phase 10: Windows WASAPI loopback companion for desktop apps.

## R2 — Python 3.14 Compatibility (MEDIUM)

**Risk:** Python 3.14 is a very recent release (some packages may have issues).

**Details:** 
- faster-whisper 1.2.1 tested and imports OK.
- CTranslate2 (faster-whisper backend) may have Windows binary availability issues.
- If CTranslate2 unavailable, fallback to openai-whisper (slower) or Deepgram cloud.

**Mitigation:** Test faster-whisper model load in Phase 4. Document fallback path.

## R3 — Faster-Whisper First-Run Latency (MEDIUM)

**Risk:** Whisper model download (small model ~150MB, medium ~500MB) blocks first use.

**Mitigation:** Pre-download model at app startup. Show download progress. Cache in `storage/models/`.

## R4 — Transcription Latency (MEDIUM)

**Risk:** Local Whisper is batch-mode, not streaming. Chunk-based processing adds latency (1-5 sec).

**Details:**
- faster-whisper processes audio chunks (e.g., 2-4 sec windows), not true streaming tokens.
- For true word-by-word streaming, need a cloud provider (Deepgram, AssemblyAI, Google STT).
- Deepgram Nova-2 provides ~200-400ms latency with real streaming.

**Mitigation:** 
- Use sliding-window chunking for local Whisper.
- Document latency expectations per provider in PERF.md.
- Deepgram free tier: 12,000 min/month (verify current terms).

## R5 — LLM Answer Latency (MEDIUM)

**Risk:** AI answer generation (GPT-4o, Gemini) takes 2-10 seconds per response.

**Mitigation:** 
- Use streaming output — display tokens as they arrive.
- Show "Generating..." spinner immediately.
- Measure and record actual latency per provider in PERF.md.

## R6 — OpenAI SDK Version (LOW)

**Risk:** openai==3.52.0 is a very recent version — API surface may differ from documented examples.

**Status:** `AsyncOpenAI` confirmed importable. Use `openai.AsyncOpenAI` for all calls.

## R7 — ffmpeg Not Installed (LOW-MEDIUM)

**Risk:** Audio format conversion (WebM → WAV/PCM for Whisper) requires ffmpeg.

**Mitigation:** Document installation in README. Provide `scripts/setup.ps1`. Phase 1 checks for ffmpeg.

## R8 — Personal Data and API Keys (LOW with mitigations)

**Risk:** Resume, transcripts, and API keys are sensitive.

**Mitigation:**
- `.env` for all keys, gitignored.
- `storage/` local directory, not committed.
- No external data sync unless explicitly added.
- Input validation and file-size limits on uploads.

## R9 — Context Window Limits (LOW)

**Risk:** Long interviews accumulate large transcripts; full transcript may exceed LLM context.

**Mitigation:** ContextManager maintains a sliding window of last N exchanges + recent transcript segments. KB retrieval returns top-K excerpts, not full documents.

## R10 — No sqlmodel pre-installed (LOW)

**Status:** Will install in Phase 1. SQLAlchemy 2.1.9 already available as the underlying engine.
