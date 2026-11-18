# Audio QA Results — Interview Copilot AI

Last updated: 2026-11-18 (Phase 3 Completed)

---

## 1. Browser & Platform Audio Support Matrix

| Browser / Platform | Tab Audio (`getDisplayMedia`) | Mic Audio (`getUserMedia`) | Support Level | Implementation Notes |
|--------------------|-------------------------------|----------------------------|---------------|----------------------|
| **Google Chrome (Windows 10/11)** | ✅ Full (with "Also share tab audio") | ✅ Full | **Primary Target** | Video track extracted & stopped immediately; audio track processed to 16kHz PCM. |
| **Microsoft Edge (Windows 10/11)** | ✅ Full (with "Also share tab audio") | ✅ Full | **Primary Target** | Chromium-based; identical capabilities to Chrome. |
| **Brave / Opera (Chromium)** | ✅ Full | ✅ Full | Supported | Standard Chromium tab audio capture. |
| **Mozilla Firefox (Windows)** | ❌ Audio track not exposed in getDisplayMedia | ✅ Full | Mic Only | Firefox does not support tab audio mixing in display media; users instructed to use mic or manual input. |
| **Google Chrome (macOS)** | ⚠️ Tab only (System audio blocked by OS) | ✅ Full | Tab & Mic | Tab audio works if sharing Chrome tab. Entire screen audio requires virtual device (BlackHole/Loopback). |
| **Standalone Desktop Apps (Zoom, Teams)** | ❌ Browser sandbox isolation | ⚠️ Mic only (User voice) | Manual / Native | Browser APIs cannot capture audio from outside the browser sandbox. Desktop companion (Phase 10) needed for loopback. |

---

## 2. Phase 3 Test Matrix & Verification

| Test Scenario | Expected Behavior | Verification Status | Implementation & Code Path |
|---------------|-------------------|---------------------|----------------------------|
| **Microphone Permission Granted** | Stream captured, live volume meter moves (0–100%), 16kHz PCM chunks emitted | ✅ Verified | `AudioCaptureProvider.startMic()` -> Web Audio AnalyserNode -> level calculation |
| **Microphone Permission Denied** | `NotAllowedError` caught, UI changes to `denied`, red error banner shown | ✅ Verified | `useAudioCapture.onError('mic', error)` sets status to `denied` with visible error message |
| **Microphone Device Selection** | `getAudioInputDevices()` enumerates all connected microphones; dropdown updates `selectedDeviceId` | ✅ Verified | `AudioCaptureProvider.getAudioInputDevices()` -> `deviceId: { exact: id }` |
| **Microphone Disconnection (Unplug)** | `navigator.mediaDevices.ondevicechange` re-enumerates devices; track ends cleanly | ✅ Verified | `track.onended` handler and `devicechange` event listener in `useAudioCapture` |
| **Google Meet Tab Audio Capture** | Screen picker appears; tab selected with audio; video track stopped; audio track processed | ✅ Verified | `getDisplayMedia({ video: true, audio: true })` -> stops video track immediately |
| **Tab Audio Checkbox Omitted** | Throws `TabAudioMissingError`, displays instruction explaining "Also share tab audio" | ✅ Verified | Detected via `audioTracks.length === 0` -> triggers `TabAudioMissingError` |
| **Tab Sharing Stopped by User** | Track ended detected, status returns to `ended`/`idle`, VU meter resets to 0% | ✅ Verified | `audioTrack.onended` handler resets status and stops processor |
| **Dual Audio Capture (Simultaneous)** | Mic and Tab audio stream concurrently with separate VU meters and separate source headers | ✅ Verified | Header byte `0x01` (Mic) and `0x02` (Tab) prepended to 16kHz 16-bit PCM buffer |
| **Audio Diagnostics Page (`/audio-test`)** | Live loopback page with real-time level meters, device dropdown, PCM chunk counter, and instructions | ✅ Verified | Route `frontend/app/audio-test/page.tsx` |

---

## 3. Audio Pipeline Specifications

- **Format:** Linear PCM, 16-bit signed integer, Little Endian, single-channel (Mono).
- **Target Sample Rate:** 16,000 Hz (Optimal for Whisper and Deepgram speech recognition).
- **Packet Structure:** 
  - Byte 0: Source identifier (`0x01` = User Microphone, `0x02` = Interviewer Tab Audio).
  - Bytes 1+: 16-bit mono PCM sample buffer (~85ms chunks at 4096 buffer size).
- **CPU Optimization:** Video tracks from `getDisplayMedia` are immediately stopped via `track.stop()`, consuming zero GPU or video decoding cycles.
