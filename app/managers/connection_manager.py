"""
ConnectionManager — central registry for all active WebSocket connections.

Design:
- Connections are stored in a dict keyed by room_id → {user_id → WebSocket}.
- An asyncio.Lock guards all mutations to prevent race conditions under concurrent connections.
- Broadcasting to a room publishes to the local in-memory connections only.
  Cross-process fan-out is handled by Redis pub/sub (see events/redis_subscriber.py).
- Stale sockets that fail to send are silently removed; the client's reconnect
  logic is responsible for re-establishing.
"""
from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

from app.core.logging import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        # room_id → {user_id → WebSocket}
        self._rooms: dict[str, dict[str, WebSocket]] = defaultdict(dict)
        # user_id → set of room_ids (a user may be in multiple rooms simultaneously)
        self._user_rooms: dict[str, set[str]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, room_id: str, user_id: str) -> None:
        await websocket.accept()
        async with self._lock:
            # Close any stale existing connection for this user+room
            existing = self._rooms[room_id].get(user_id)
            if existing is not None:
                try:
                    await existing.close(code=4000)
                except Exception:
                    pass

            self._rooms[room_id][user_id] = websocket
            self._user_rooms[user_id].add(room_id)

        logger.info("ws_connected", user_id=user_id, room_id=room_id)

    async def disconnect(self, room_id: str, user_id: str) -> None:
        async with self._lock:
            self._rooms[room_id].pop(user_id, None)
            if not self._rooms[room_id]:
                del self._rooms[room_id]
            self._user_rooms[user_id].discard(room_id)
            if not self._user_rooms[user_id]:
                del self._user_rooms[user_id]

        logger.info("ws_disconnected", user_id=user_id, room_id=room_id)

    async def broadcast_to_room(self, room_id: str, message: dict[str, Any]) -> None:
        """Send message to all connections in a room. Remove stale sockets on failure."""
        async with self._lock:
            sockets = dict(self._rooms.get(room_id, {}))

        stale: list[str] = []
        for uid, ws in sockets.items():
            try:
                await ws.send_json(message)
            except Exception:
                stale.append(uid)

        if stale:
            async with self._lock:
                for uid in stale:
                    self._rooms[room_id].pop(uid, None)
                    self._user_rooms[uid].discard(room_id)

    async def send_to_user(self, user_id: str, message: dict[str, Any]) -> None:
        """Send a direct message to a specific user across all their rooms."""
        async with self._lock:
            room_ids = list(self._user_rooms.get(user_id, set()))

        for room_id in room_ids:
            async with self._lock:
                ws = self._rooms.get(room_id, {}).get(user_id)
            if ws:
                try:
                    await ws.send_json(message)
                except Exception:
                    await self.disconnect(room_id, user_id)

    def is_connected(self, user_id: str) -> bool:
        return user_id in self._user_rooms and bool(self._user_rooms[user_id])

    def room_user_ids(self, room_id: str) -> list[str]:
        return list(self._rooms.get(room_id, {}).keys())

    def total_connections(self) -> int:
        return sum(len(users) for users in self._rooms.values())


# Singleton — one manager per process. Redis pub/sub bridges across processes.
manager = ConnectionManager()
