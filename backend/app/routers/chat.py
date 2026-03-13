"""WebSocket chat endpoint for streaming agent communication."""

import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import structlog

logger = structlog.get_logger()
router = APIRouter()


def _get_state():
    from ..main import app_state
    return app_state


@router.websocket("/ws/chat/{client_id}")
async def websocket_chat(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for streaming chat with the anonymization agent.

    Client sends: {"ticket_id": int, "message": str}
    Server sends: {"type": "token"|"complete"|"error"|"info", "data": str, "ticket_id": int}
    """
    state = _get_state()
    ws_manager = state["ws_manager"]
    agent = state["agent"]

    await ws_manager.connect(websocket, client_id)

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws_manager.send_error(client_id, "Invalid JSON message")
                continue

            action = data.get("action", "chat")

            # Ping keepalive - just ignore
            if action == "ping":
                continue

            ticket_id = data.get("ticket_id")
            message = data.get("message", "").strip()

            if not ticket_id:
                await ws_manager.send_error(client_id, "ticket_id is required")
                continue

            try:
                if action == "summary":
                    # Generate initial summary for a ticket
                    await agent.generate_initial_summary(ticket_id, client_id)
                elif action == "chat" and message:
                    # Process chat message
                    await agent.chat(ticket_id, message, client_id)
                else:
                    await ws_manager.send_error(
                        client_id, "message is required for chat action", ticket_id
                    )
            except Exception as e:
                logger.error(
                    "ws_chat_error",
                    client_id=client_id,
                    ticket_id=ticket_id,
                    error=str(e),
                )
                await ws_manager.send_error(
                    client_id,
                    f"Error procesando mensaje: {str(e)}",
                    ticket_id,
                )

    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)
    except Exception as e:
        logger.error("ws_unexpected_error", client_id=client_id, error=str(e))
        ws_manager.disconnect(client_id)
