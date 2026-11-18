# Windows WASAPI Loopback Desktop Companion (PoC)

Captures permitted interviewer audio from **Zoom Desktop**, **Microsoft Teams Desktop**, or any Windows desktop audio output using native **Windows WASAPI Loopback** and streams it directly into the existing Interview Copilot AI FastAPI backend (`/ws/audio/{session_id}`).

No existing backend or frontend services are rewritten — open your session at `http://localhost:3000/session/<session_id>` and watch live transcripts, detected questions, and streaming AI answers appear in real time.

## Setup

```powershell
cd desktop_companion
pip install -r requirements.txt
```

## List Windows WASAPI Devices

```powershell
python wasapi_bridge.py --list-devices
```

## Stream Zoom / Teams Audio to an Active Session

1. Create and open a session in the web dashboard (`http://localhost:3000`).
2. Copy the session UUID from the URL (`/session/<SESSION_ID>`).
3. Start the WASAPI bridge:

```powershell
# System audio loopback only (Interviewer voice from Zoom/Teams)
python wasapi_bridge.py --session-id <SESSION_ID>

# Both System Loopback (Interviewer) + Microphone (Your voice)
python wasapi_bridge.py --session-id <SESSION_ID> --mic
```

Press `Ctrl+C` at any time to flush remaining audio and stop capture cleanly.
