# Performance Baselines — Interview Copilot AI

Last updated: 2026-11-18 (Phase 4 Measurements Recorded)

> Measurements are added as each phase completes. Never promise a latency not measured.

---

## Measurement Points

| Stage | Metric | Target | Measured |
|-------|--------|--------|----------|
| Audio → Transcript (`faster-whisper` tiny, int8, CPU) | Warm inference (3.4s clip) | < 5 sec | **312 ms** (cold load+download: 15,558 ms) |
| Audio → Transcript (end-to-end buffer + silence gate + STT) | Utterance finalize delay | < 5 sec | **~912 ms** (600ms silence gate + 312ms STT) |
| Audio → Transcript (Deepgram Nova-2 HTTP PCM) | Chunk latency | < 500 ms | Not yet benchmarked (requires `DEEPGRAM_API_KEY`) |
| Transcript → Question Detected | Detection latency | < 200 ms | **0.281 ms avg** (1.496 ms max) |
| Question → Answer Start (Pipeline overhead, mocked LLM) | Context + WS dispatch | < 100 ms | **~3 ms** (ContextManager + WS dispatch) |
| Question → Answer Start (`gemini-3.5-flash-lite` live API) | TTFT (time-to-first-token) | < 2 sec | **611–1,465 ms** (measured live) |
| Question → Answer Complete (`gemini-3.5-flash-lite` live API) | Total generation (`short`) | < 8 sec | **825–1,628 ms** (measured live) |
| Total: Audio → Displayed Answer (Local Whisper + Gemini 3.5 Flash Lite) | End-to-end live pipeline | < 15 sec | **~1.5–2.4 sec** to first token, **~1.7–2.5 sec** complete |

---

## Phase 4 — Transcription Latency (Measured)

**Test Hardware:** Local Windows CPU (Python 3.14.7, `faster-whisper` 1.2.1, `int8` compute type)
**Fixture:** `backend/tests/fixtures/sample_audio.wav` (16kHz 16-bit mono WAV, 3.38s duration, spoken: *"What is SQL injection and how do you prevent it?"*)

| Run | Model | Latency | Output Text | Confidence |
|-----|-------|---------|-------------|------------|
| Cold (first run: HF download + model init + inference) | `whisper:tiny` | 15,558 ms | `"What is SQL injection and how do you prevent it?"` | 0.70 |
| Warm (cached model in memory) | `whisper:tiny` | **312 ms** | `"What is SQL injection and how do you prevent it?"` | 0.70 |

**Key Observations:**
1. Direct browser 16kHz PCM → `numpy.float32` eliminates `ffmpeg` transcoding overhead completely (~0ms decode cost).
2. Energy-based VAD silence gating in `TranscriptManager` drops silent chunks in < 1ms without invoking Whisper.
3. End-to-end utterance-end → transcript display latency on warm local CPU is **~0.9–1.0s** (600ms trailing silence threshold + ~312ms Whisper inference).

---

## Phase 5 — Question Detection Latency (Measured)

**Fixture:** `backend/tests/fixtures/sample_interview.jsonl` (19 turns, 10 detected questions)
- **Average latency:** `0.281 ms`
- **Maximum latency:** `1.496 ms`
- **Overhead:** Negligible (< 0.2% of total pipeline budget; zero external network calls).

## Phase 6 — Answer Generation Latency (Measured Live)

- **Pipeline overhead (ContextManager DB queries + Prompt assembly + WebSocket streaming dispatch):** **~3 ms**.
- **Live Cloud LLM (`gemini:gemini-3.5-flash-lite`):**
  - Technical question (`"What is SQL injection?"`, `short`): **TTFT = 1,465 ms**, **Total = 1,628 ms**.
  - Grounded personal question (`"Explain your previous project."`, `short`, no resume): **TTFT = 611 ms**, **Total = 825 ms** (honored anti-fabrication Grounding Guard with `[Needs customization ...]` prefix).
- **Combined End-to-End Critical Path (Audio silence end → Complete displayed answer):** **~1.7–2.5 seconds** (600 ms silence gate + 312 ms `whisper:tiny` + 0.28 ms question detection + 3 ms context/dispatch + 825–1,628 ms Gemini 3.5 Flash Lite).
