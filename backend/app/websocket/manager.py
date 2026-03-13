"""WebSocket connection manager for real-time chat streaming."""

import json
from typing import Dict, Optional
from fastapi import WebSocket
import structlog

logger = structlog.get_logger()


class ConnectionManager:
    """Manages WebSocket connections for streaming chat responses."""

    def __init__(self):
        self._connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self._connections[client_id] = websocket
        logger.info("ws_connected", client_id=client_id)

    def disconnect(self, client_id: str):
        self._connections.pop(client_id, None)
        logger.info("ws_disconnected", client_id=client_id)

    def is_connected(self, client_id: str) -> bool:
        return client_id in self._connections

    async def send_message(self, client_id: str, data: dict):
        """Send a JSON message to a specific client."""
        ws = self._connections.get(client_id)
        if ws:
            try:
                await ws.send_json(data)
            except Exception as e:
                logger.error("ws_send_error", client_id=client_id, error=str(e))
                self.disconnect(client_id)

    async def send_token(self, client_id: str, token: str, ticket_id: int = None):
        """Send a streaming token to the client."""
        await self.send_message(client_id, {
            "type": "token",
            "data": token,
            "ticket_id": ticket_id,
        })

    async def send_complete(self, client_id: str, full_response: str, ticket_id: int = None):
        """Signal that a response is complete."""
        await self.send_message(client_id, {
            "type": "complete",
            "data": full_response,
            "ticket_id": ticket_id,
        })

    async def send_error(self, client_id: str, error: str, ticket_id: int = None):
        """Send an error message."""
        await self.send_message(client_id, {
            "type": "error",
            "data": error,
            "ticket_id": ticket_id,
        })

    async def send_info(self, client_id: str, info: str, ticket_id: int = None):
        """Send an informational message."""
        await self.send_message(client_id, {
            "type": "info",
            "data": info,
            "ticket_id": ticket_id,
        })

    async def broadcast(self, data: dict):
        """Broadcast a message to all connected clients."""
        disconnected = []
        for client_id, ws in self._connections.items():
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.append(client_id)
        for cid in disconnected:
            self.disconnect(cid)
