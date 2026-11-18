"""
Windows WASAPI Loopback Audio Bridge PoC — Desktop Companion for Interview Copilot AI.

Captures permitted Windows system audio (e.g. Zoom or Microsoft Teams desktop apps)
via native WASAPI loopback and/or microphone audio, converts to 16kHz 16-bit mono PCM,
and streams directly into the existing FastAPI backend at /ws/audio/{session_id}.

Zero rewrite of backend services: uses the exact same wire format as the web frontend:
  - Byte 0: 0x01 (Microphone / Me) or 0x02 (System Loopback / Interviewer)
  - Bytes 1+: 16,000 Hz, 16-bit signed little-endian mono PCM

Transparency: Always displays an explicit live capture banner and VU level meter.
"""
import argparse
import asyncio
import json
import signal
import sys
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

SOURCE_MIC_BYTE = 0x01
SOURCE_LOOPBACK_BYTE = 0x02
TARGET_SAMPLE_RATE = 16000
CHUNK_FRAMES = 1600  # 100ms chunks at 16kHz


@dataclass
class AudioDeviceSummary:
    id: str
    name: str
    is_loopback: bool


def float32_to_pcm16_frame(samples: np.ndarray, source_byte: int) -> bytes:
    """
    Convert mono or multi-channel float32 samples (-1.0..1.0) into a tagged
    16-bit little-endian mono PCM WebSocket frame: [source_byte] + pcm16 bytes.
    """
    arr = np.asarray(samples, dtype=np.float32)
    if arr.ndim == 2:
        # Downmix multi-channel to mono
        arr = np.mean(arr, axis=1)
    arr = np.clip(arr, -1.0, 1.0)
    int16_samples = (arr * 32767.0).astype("<i2")
    return bytes([source_byte]) + int16_samples.tobytes()


def compute_rms_level(samples: np.ndarray) -> float:
    """Compute normalized 0.0..1.0 visual VU meter level from float32 samples."""
    arr = np.asarray(samples, dtype=np.float32)
    if arr.size == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(arr * arr)))
    return min(1.0, rms * 4.0)


def list_wasapi_devices() -> List[AudioDeviceSummary]:
    """Enumerate available Windows WASAPI microphones and speaker loopback endpoints."""
    import soundcard as sc

    mics = sc.all_microphones(include_loopback=True)
    return [
        AudioDeviceSummary(
            id=str(m.id),
            name=str(m.name),
            is_loopback=bool(getattr(m, "isloopback", False)),
        )
        for m in mics
    ]


def get_default_loopback_device():
    """Return the Windows WASAPI loopback recorder bound to the default system speaker."""
    import soundcard as sc

    speaker = sc.default_speaker()
    return sc.get_microphone(id=str(speaker.name), include_loopback=True)


def get_default_mic_device():
    """Return the default Windows microphone recorder."""
    import soundcard as sc

    return sc.default_microphone()


async def _capture_device_loop(
    device,
    source_byte: int,
    label: str,
    queue: asyncio.Queue,
    stop_event: asyncio.Event,
    sample_rate: int = TARGET_SAMPLE_RATE,
    chunk_frames: int = CHUNK_FRAMES,
) -> None:
    """Continuously record from a WASAPI endpoint in a worker thread and push PCM frames."""

    def _record_blocking(recorder):
        return recorder.record(numframes=chunk_frames)

    with device.recorder(samplerate=sample_rate, channels=1) as recorder:
        while not stop_event.is_set():
            data = await asyncio.to_thread(_record_blocking, recorder)
            frame = float32_to_pcm16_frame(data, source_byte)
            level = compute_rms_level(data)
            await queue.put((label, frame, level))


async def run_bridge(
    session_id: str,
    ws_base_url: str = "ws://localhost:8000",
    capture_loopback: bool = True,
    capture_mic: bool = False,
    language: str = "en",
) -> None:
    """Connect to existing FastAPI /ws/audio/{session_id} and stream WASAPI loopback/mic PCM."""
    import websockets

    ws_url = f"{ws_base_url.rstrip('/')}/ws/audio/{session_id}"
    stop_event = asyncio.Event()
    queue: asyncio.Queue = asyncio.Queue(maxsize=64)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    tasks: List[asyncio.Task] = []

    print("=" * 68)
    print("  INTERVIEW COPILOT AI — WINDOWS WASAPI AUDIO BRIDGE (PERMITTED USE)")
    print(f"  Target Backend : {ws_url}")
    print(f"  Language       : {language}")
    print("  STATUS         : VISIBLE LIVE CAPTURE ACTIVE — Press Ctrl+C to stop")
    print("=" * 68)

    if capture_loopback:
        lp_dev = get_default_loopback_device()
        print(f"  [SYSTEM LOOPBACK -> 0x02 Interviewer] {lp_dev.name}")
        tasks.append(
            asyncio.create_task(
                _capture_device_loop(lp_dev, SOURCE_LOOPBACK_BYTE, "SYS", queue, stop_event)
            )
        )

    if capture_mic:
        mic_dev = get_default_mic_device()
        print(f"  [MICROPHONE      -> 0x01 Me         ] {mic_dev.name}")
        tasks.append(
            asyncio.create_task(
                _capture_device_loop(mic_dev, SOURCE_MIC_BYTE, "MIC", queue, stop_event)
            )
        )

    if not tasks:
        print("No capture source selected. Enable --loopback and/or --mic.")
        return

    try:
        async with websockets.connect(ws_url, max_size=None) as ws:
            await ws.send(json.dumps({"type": "config", "language": language}))
            print("  Connected to FastAPI backend. Streaming audio...\n")

            while not stop_event.is_set():
                try:
                    label, frame, level = await asyncio.wait_for(queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue

                await ws.send(frame)
                bars = "#" * int(level * 24)
                sys.stdout.write(f"\r  LIVE [{label}] |{bars:<24}| {int(level * 100):3d}%")
                sys.stdout.flush()

            await ws.send(json.dumps({"type": "control", "action": "flush"}))
    except KeyboardInterrupt:
        stop_event.set()
    finally:
        stop_event.set()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        print("\n  WASAPI Audio Bridge stopped cleanly.")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Windows WASAPI Loopback Bridge for Interview Copilot AI"
    )
    parser.add_argument("--list-devices", action="store_true", help="List Windows WASAPI devices and exit")
    parser.add_argument("--session-id", type=str, help="Active interview session UUID from dashboard")
    parser.add_argument("--ws-url", type=str, default="ws://localhost:8000", help="Backend WebSocket base URL")
    parser.add_argument("--no-loopback", action="store_true", help="Disable system speaker loopback capture")
    parser.add_argument("--mic", action="store_true", help="Also capture microphone audio")
    parser.add_argument("--language", type=str, default="en", help="Transcription language code (default: en)")
    args = parser.parse_args(argv)

    if args.list_devices:
        devices = list_wasapi_devices()
        print("Windows WASAPI Audio Endpoints:")
        for d in devices:
            kind = "LOOPBACK (System Audio)" if d.is_loopback else "MICROPHONE"
            print(f"  - [{kind}] {d.name}")
        return 0

    if not args.session_id:
        parser.error("--session-id is required unless --list-devices is specified.")

    try:
        asyncio.run(
            run_bridge(
                session_id=args.session_id,
                ws_base_url=args.ws_url,
                capture_loopback=not args.no_loopback,
                capture_mic=args.mic,
                language=args.language,
            )
        )
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
