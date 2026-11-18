"""
Session WebSocket endpoint — pushes real-time transcript, question,
answer, status, and error events to the browser dashboard.
"""
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.websockets.manager import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/session/{session_id}")
async def session_websocket(websocket: WebSocket, session_id: str):
    """
    Pushes structured JSON events to the browser:
      transcript, question, answer_chunk, answer_complete, status, error, pong
    """
    await ws_manager.connect_session_ws(session_id, websocket)

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if "text" in message and message["text"]:
                try:
                    data = json.loads(message["text"])
                    if data.get("type") == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}))
                except json.JSONDecodeError:
                    pass
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("Session WS error for session %s: %s", session_id, e)
    finally:
        ws_manager.disconnect_session_ws(session_id, websocket)
