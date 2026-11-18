"""
Audio WebSocket endpoint — receives binary PCM audio chunks from the browser,
routes them through TranscriptManager -> SpeechToTextProvider, and broadcasts
live transcript events to /ws/session/{session_id}.
"""
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.websockets.manager import ws_manager
from app.core.exceptions import ProviderError

logger = logging.getLogger(__name__)
router = APIRouter()

SOURCE_BYTE_MAP = {
    0x01: "mic",
    0x02: "tab",
}


@router.websocket("/ws/audio/{session_id}")
async def audio_websocket(websocket: WebSocket, session_id: str):
    """
    Receives binary 16kHz 16-bit mono PCM audio frames from the browser.
    Frame format:
      - Byte 0: source identifier (0x01 = mic, 0x02 = tab)
      - Bytes 1+: raw linear16 PCM bytes

    Also accepts JSON control frames:
      - {"type": "control", "action": "pause" | "resume" | "flush" | "end"}
      - {"type": "config", "language": "en"}
    """
    await websocket.accept()
    logger.info("Audio WS connected for session %s", session_id)

    tm = ws_manager.get_or_create_transcript_manager(session_id)

    try:
        while True:
            message = await websocket.receive()
            msg_type = message.get("type")
            if msg_type == "websocket.disconnect":
                break

            if "bytes" in message and message["bytes"]:
                raw: bytes = message["bytes"]
                if len(raw) < 2:
                    continue
                header = raw[0]
                source = SOURCE_BYTE_MAP.get(header, "mic")
                pcm_data = raw[1:]

                await ws_manager.set_audio_source_state(session_id, source, True)
                try:
                    await tm.process_audio_chunk(source, pcm_data)
                except ProviderError as pe:
                    logger.error("STT ProviderError for session %s: %s", session_id, pe)
                    await ws_manager.broadcast(
                        session_id,
                        {
                            "type": "error",
                            "code": "STT_PROVIDER_ERROR",
                            "message": pe.message,
                        },
                    )
                except Exception as exc:
                    logger.error("Transcription error for session %s: %s", session_id, exc)
                    await ws_manager.broadcast(
                        session_id,
                        {
                            "type": "error",
                            "code": "TRANSCRIPTION_ERROR",
                            "message": "Failed to transcribe audio chunk.",
                        },
                    )

            elif "text" in message and message["text"]:
                try:
                    payload = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue

                frame_type = payload.get("type")
                if frame_type == "control":
                    action = payload.get("action")
                    if action == "pause":
                        tm.set_paused(True)
                        await tm.flush()
                        await ws_manager.broadcast(
                            session_id,
                            {
                                "type": "status",
                                "session_id": session_id,
                                "session_status": "paused",
                                "language": tm.language,
                            },
                        )
                    elif action == "resume":
                        tm.set_paused(False)
                        await ws_manager.broadcast(
                            session_id,
                            {
                                "type": "status",
                                "session_id": session_id,
                                "session_status": "active",
                                "language": tm.language,
                            },
                        )
                    elif action == "flush":
                        await tm.flush()
                    elif action == "end":
                        await ws_manager.cleanup_session(session_id)
                        await ws_manager.broadcast(
                            session_id,
                            {
                                "type": "status",
                                "session_id": session_id,
                                "session_status": "ended",
                            },
                        )
                        break
                elif frame_type == "config":
                    language = payload.get("language")
                    if language:
                        tm.set_language(language)
                        logger.info("Session %s language set to '%s'", session_id, language)
                        await ws_manager.broadcast(
                            session_id,
                            {
                                "type": "status",
                                "session_id": session_id,
                                "session_status": "paused" if tm.paused else "active",
                                "language": tm.language,
                            },
                        )

    except WebSocketDisconnect:
        logger.info("Audio WS disconnected for session %s", session_id)
    except Exception as e:
        logger.error("Audio WS error for session %s: %s", session_id, e)
    finally:
        # Flush remaining audio so final spoken words are not lost on disconnect
        try:
            await tm.flush()
        except Exception:
            pass
        await ws_manager.set_audio_source_state(session_id, "mic", False)
        await ws_manager.set_audio_source_state(session_id, "tab", False)
