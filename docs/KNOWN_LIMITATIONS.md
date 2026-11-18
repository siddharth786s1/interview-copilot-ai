# Known Limitations — Interview Copilot AI

Last updated: 2026-11-18 (Phase 9 QA Hardening Completed)

> This document is intentionally honest about what the application can and cannot do in its current web-first architecture.

---

## 1. Audio Capture & Platform Boundaries

1. **Zoom & Microsoft Teams Desktop Applications:** Browser sandboxes cannot capture system audio from standalone desktop applications. When interviewing on Zoom or Teams desktop, use **Microphone-only** capture or the **Manual Question Input** box in the live workspace. Capturing Zoom/Teams desktop audio requires a Windows WASAPI loopback companion (Phase 10, optional).
2. **Google Meet (Browser Tab Audio):** Supported in **Chrome** and **Microsoft Edge** on Windows/Linux/macOS when the user explicitly selects the meeting browser tab AND checks **"Also share tab audio"**. The application cannot force or pre-check that browser dialog option; if omitted, the UI raises a visible `TabAudioMissingError` explaining how to enable it.
3. **macOS System Audio:** Browser APIs cannot capture full macOS system audio without a third-party virtual audio device (such as BlackHole or Loopback).
4. **Mozilla Firefox:** `getDisplayMedia` does not expose tab audio tracks by default. Use Chrome or Edge for tab audio capture.
5. **ScriptProcessorNode Deprecation:** `AudioCaptureProvider` currently uses `ScriptProcessorNode` for 16kHz PCM resampling because it works synchronously across browsers without external worklet bundling; migrating to `AudioWorkletNode` is a clean future optimization if audio glitches appear under heavy CPU load.

---

## 2. Speech Recognition & Speaker Identification

6. **Local Whisper (`faster-whisper`) Is Chunked, Not True Token Streaming:** Whisper processes rolling utterance windows triggered by energy-based silence gating (`600 ms`) or max utterance length (`5.0 s`). Warm CPU inference on `whisper:tiny` was measured at **312 ms** (~912 ms total utterance-end to transcript display); larger models (`base`, `small`, `medium`) trade higher latency for accuracy. First run downloads the model weights from HuggingFace (~75 MB for `tiny`, ~145 MB for `base`). For true sub-500 ms cloud streaming, configure `STT_PROVIDER=deepgram` with a `DEEPGRAM_API_KEY`.
7. **Speaker Labels Are Best-Effort:** Speaker separation relies on audio source tagging (`0x02` tab → `Interviewer`, `0x01` mic → `Me`). If multiple interviewers speak on the same tab, or if running in mic-only mode near speakers, speaker attribution is best-effort rather than true voice-print diarization.

---

## 3. Question Detection

8. **Heuristic Pattern-Based Detection:** The engine achieves 1.00 Precision / 1.00 Recall on the 19-turn labeled interview test set in `0.28 ms` average latency with zero LLM cost, while suppressing meeting logistics (*"Can you hear me?"*) and small talk. However, purely declarative indirect prompts without interrogative or cue verbs (e.g. *"I'd be curious about database locking."*) may occasionally be skipped. The **Manual Question Input** in the live workspace is always available as an instant fallback.

---

## 4. AI Answer Generation & Knowledge Base

9. **Cloud LLM Key Required for Live AI Answers:** Local Whisper handles speech-to-text at \$0, but generating live interview answers requires setting either `GOOGLE_API_KEY` (Gemini 2.0 Flash free tier) or `OPENAI_API_KEY` in `.env`. Without a key, the live workspace surfaces an explicit `LLM_CONFIG_ERROR` banner instead of faking answers.
10. **Strict Grounding Guard:** The AI is explicitly prohibited from inventing employers, roles, projects, metrics, or certifications. When personal-background questions (*"Tell me about yourself"*, *"Explain your previous project"*) are asked without an uploaded resume, the answer is flagged with a visible **Customization Needed** notice and uses placeholders.
11. **BM25 Keyword Retrieval (No Vector Search Yet):** The Personal Knowledge Base uses fast local BM25 ranking (`rank-bm25`). Purely conceptual synonyms that share zero keywords with uploaded notes will not match until corpus size justifies adding semantic embeddings.
12. **Mock Interview Offline Fallback:** When no LLM API key is configured, Mock Interview Mode transparently falls back to its built-in question bank (`offline_bank`) and keyword-concept rubric (`local_rubric`), visibly labelled in the UI. Live LLM coaching activates automatically once an API key is configured.

---

## 5. Scope & Deployment

13. **Single-User Local-First Architecture:** Designed for one local user running on `localhost` with SQLite. There is no multi-tenant auth, billing, or cloud sync.
14. **Permitted & Transparent Use Only:** No covert recording, hidden overlays, screen-share evasion, or proctoring bypass exists in this codebase.
