"""WebSocket manager for real-time HUD updates."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections and broadcasts updates."""

    def __init__(self):
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and track a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)
        logger.debug(f"WebSocket connected. Total: {len(self._connections)}")

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            self._connections.discard(websocket)
        logger.debug(f"WebSocket disconnected. Total: {len(self._connections)}")

    async def broadcast(self, message: dict) -> int:
        """Broadcast a message to all connected clients.

        Returns:
            Number of clients that received the message
        """
        if not self._connections:
            return 0

        json_msg = json.dumps(message)
        disconnected: list[WebSocket] = []
        sent_count = 0

        async with self._lock:
            connections = list(self._connections)

        for conn in connections:
            try:
                await conn.send_text(json_msg)
                sent_count += 1
            except Exception:
                disconnected.append(conn)

        # Clean up any failed connections
        if disconnected:
            async with self._lock:
                for conn in disconnected:
                    self._connections.discard(conn)

        return sent_count

    async def broadcast_data_changed(
        self, data_type: str, path: str | None = None
    ) -> int:
        """Broadcast that specific data has changed.

        Args:
            data_type: Type of data that changed (sessions, skills, memory, etc.)
            path: Optional path to the file that changed
        """
        return await self.broadcast(
            {
                "type": "data_changed",
                "data_type": data_type,
                "path": path,
            }
        )

    async def broadcast_cache_invalidation(self, cache_keys: list[str]) -> int:
        """Broadcast that specific cache keys should be invalidated."""
        return await self.broadcast(
            {
                "type": "cache_invalidate",
                "keys": cache_keys,
            }
        )

    def get_connection_count(self) -> int:
        """Return number of active connections."""
        return len(self._connections)


# Global WebSocket manager instance
ws_manager = WebSocketManager()
