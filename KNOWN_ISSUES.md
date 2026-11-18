# Known Issues — Interview Copilot AI

---

## OPEN

### KI-001: ffmpeg not installed
- **What:** `ffmpeg` is not in PATH.
- **Why:** Not pre-installed on this Windows system.
- **Status:** **Mitigated / Resolved for live streaming (D008)** — Browser `AudioCaptureProvider` streams raw 16kHz 16-bit mono PCM directly to `WhisperProvider` via `numpy.frombuffer`, so live transcription works with zero `ffmpeg` dependency. Only needed if arbitrary compressed audio files (MP3/M4A) are uploaded in the future.

### KI-002: OpenAI SDK version
- **What:** `openai==3.52.0` — this is a very recent version.
- **Status:** Verified compatible with `AsyncOpenAI` streaming in Phase 6 (`openai_provider.py`).

---

## RESOLVED

### KI-003: Python 3.14 package compatibility (Resolved 2026-11-18)
- `sqlmodel`, `aiosqlite`, `faster-whisper`, `google-genai`, `openai`, `rank-bm25`, `python-docx`, and `pypdf` all installed and passed 53 automated tests on Python 3.14.7 with zero issues.
