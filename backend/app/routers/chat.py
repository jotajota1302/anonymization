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

    Also emits {"type":"heartbeat"} every 20s server-side so Istio/Envoy
    idle timeouts (default 30s on many ingress controllers) don't tear the
    socket down during long LLM streams or when the operator is idle.
    """
    import asyncio as _asyncio

    state = _get_state()
    ws_manager = state["ws_manager"]
    agent = state["agent"]

    await ws_manager.connect(websocket, client_id)

    async def _heartbeat():
        try:
            while True:
                await _asyncio.sleep(20)
                try:
                    await websocket.send_json({"type": "heartbeat"})
                except Exception:
                    break
        except _asyncio.CancelledError:
            pass

    hb_task = _asyncio.create_task(_heartbeat())

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws_manager.send_error(client_id, "Invalid JSON message")
                continue

            action = data.get("action", "chat")

            # Ping keepalive — reply with pong to keep bidirectional traffic
            # flowing through Istio/Envoy proxies
            if action == "ping":
                try:
                    await websocket.send_json({"type": "pong"})
                except Exception:
                    pass
                continue

            ticket_id = data.get("ticket_id")
            message = data.get("message", "").strip()

            if not ticket_id:
                await ws_manager.send_error(client_id, "ticket_id is required")
                continue

            try:
                # Verify LLM is still functional (token may have expired)
                if agent and hasattr(agent, "check_llm_ready"):
                    ready, err = agent.check_llm_ready()
                    if not ready:
                        await ws_manager.send_error(client_id, err, ticket_id)
                        continue

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
    finally:
        hb_task.cancel()
