# Windows Desktop Companion Feasibility & Architecture (Phase 10)

Last updated: 2026-11-18

---

## 1. Problem Statement

In Phases 1–9, Interview Copilot AI runs as a local-first web application. Browser audio capture (`getDisplayMedia`) works well for **Google Meet in Chrome/Edge**, but browser sandboxes intentionally prevent capturing audio from standalone desktop applications (**Zoom Desktop**, **Microsoft Teams Desktop**).

To capture permitted interviewer audio from Zoom or Teams desktop on Windows without rewriting any backend services, we need a Windows-native **WASAPI Loopback** capture component that connects directly to the existing FastAPI WebSocket endpoint (`/ws/audio/{session_id}`).

---

## 2. Windows System-Audio Capture Requirements

- **OS API:** Windows Audio Session API (**WASAPI**) with `AUDCLNT_STREAMFLAGS_LOOPBACK` on the active render (speaker/headset) endpoint.
- **Dual Independent Streams:**
  1. **System Loopback (Interviewer):** Captures audio played through the selected speaker/headset output (`0x02` frame header → backend `"tab"` / `"Interviewer"` stream).
  2. **Microphone Input (Candidate):** Captures the user's microphone independently (`0x01` frame header → backend `"mic"` / `"Me"` stream).
- **Wire Protocol (Zero Backend Changes):**
  - Target endpoint: `ws://localhost:8000/ws/audio/{session_id}`
  - Format: 16,000 Hz, 16-bit signed little-endian mono PCM, prefixed with 1 source byte (`0x01` or `0x02`).
  - Existing `TranscriptManager`, `QuestionDetectionEngine`, `ContextManager`, `AnswerGenerationService`, and live Next.js dashboard work unchanged.
- **Transparency & Ethics:** Audio capture must be explicitly started by the user, display a prominent live capture indicator + VU level readout at all times, and never implement covert capture or screen-share evasion.

---

## 3. Tauri vs Electron vs Python WASAPI Companion Bridge

| Dimension | **Tauri v2 (Rust + WebView2)** | **Electron (Chromium + Node.js)** | **Python WASAPI Companion Bridge (PoC)** |
|-----------|--------------------------------|-----------------------------------|------------------------------------------|
| **Windows WASAPI Loopback** | Native via Rust `wasapi` / `cpal` crates (excellent low-level control) | Requires native C++ N-API addon or `electron-audio-loopback` + `desktopCapturer` quirks | Native COM WASAPI loopback via `soundcard` (pure Python + `cffi`, verified live on this Windows host) |
| **Installer / Binary Size** | ~8–15 MB (uses Windows WebView2) | ~120–180 MB (bundles Chromium + Node) | ~0 MB extra (reuses existing Python backend env) |
| **Idle RAM Footprint** | ~40–70 MB | ~250–400 MB | ~35 MB |
| **Build Toolchain Required** | Rust (`cargo`/`rustup`) + MSVC Build Tools (**not currently installed**) | Node.js + node-gyp / MSVC for native WASAPI addon | Python 3.14 + `soundcard` (**installed & verified today**) |
| **Existing Next.js UI Reuse** | Wraps Next.js static/local UI cleanly inside WebView2 | Wraps Next.js UI cleanly | Opens existing Next.js dashboard in user's browser while bridging audio |
| **Backend Rewrite Required** | **None** — streams identical PCM frames to `/ws/audio/{session_id}` | **None** — streams identical PCM frames to `/ws/audio/{session_id}` | **None** — streams identical PCM frames to `/ws/audio/{session_id}` |
| **Best Fit** | Best long-term standalone `.exe` desktop wrapper | Heavier; justified only if custom Chromium flags are needed | Best immediate personal companion PoC (zero extra toolchain) |

---

## 4. Recommendation

1. **Immediate Personal Use (Implemented in `desktop_companion/`):** Use the lightweight **Python Windows WASAPI Loopback Bridge** (`desktop_companion/wasapi_bridge.py`). It verified live on this host against `Speakers (Realtek(R) Audio)` (`isloopback=True`, 16kHz mono float32 → 16-bit PCM), adds zero extra runtime or build toolchains, and connects straight into `/ws/audio/{session_id}` while you view answers on the existing Next.js dashboard at `http://localhost:3000/session/<id>`.
2. **Future Packaged App (Optional):** If a single clickable Windows `.exe` with system tray icon is desired later, choose **Tauri v2** over Electron (10x smaller binary, 5x lower RAM, first-class Rust WASAPI bindings) and point its WebView directly at the existing frontend + backend without modifying any AI or transcription services.

---

## 5. Host Verification Record (2026-11-18)

- **Windows Host APIs Detected:** `MME`, `Windows DirectSound`, `Windows WASAPI`, `Windows WDM-KS`
- **Verified Default Speaker Loopback:** `Speakers (Realtek(R) Audio)` (`isloopback=True`)
- **Verified Capture:** `1600` frames at `16,000 Hz`, mono `float32` → converted to `0x02` + 3,200 bytes linear16 PCM and verified end-to-end against FastAPI `/ws/audio/{session_id}` in `backend/tests/integration/test_desktop_companion.py`.
