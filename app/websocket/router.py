"""
WebSocket endpoint — /ws/chat/{room_id}

Connection lifecycle:
  1. Authenticate via ?token= query param (browsers can't set WS headers).
  2. Verify room membership.
  3. Register connection in ConnectionManager.
  4. Broadcast presence:online event.
  5. Run message loop: receive JSON → dispatch to handler.
  6. On disconnect: clean up manager, broadcast presence:offline, update last_seen.

Heartbeat:
  Client sends {"type": "ping"} → server responds {"type": "pong"}.
  If no ping is received within 90s, the server closes the connection.
  (Uvicorn's WebSocket layer will close stale TCP connections independently.)
"""
from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.dependencies.auth import get_current_user_ws
from app.dependencies.database import get_db
from app.managers.connection_manager import manager
from app.models.user import User
from app.repositories.room_repo import RoomRepository
from app.repositories.user_repo import UserRepository
from app.services.presence_service import refresh_presence, set_offline, set_online
from app.websocket.handlers import (
    handle_chat_message,
    handle_mark_read,
    handle_typing_start,
    handle_typing_stop,
)

router = APIRouter()
logger = get_logger(__name__)

_HEARTBEAT_INTERVAL = 60  # seconds — refresh presence TTL
_DISPATCH = {
    "chat_message": handle_chat_message,
    "typing_start": handle_typing_start,
    "typing_stop": handle_typing_stop,
    "mark_read": handle_mark_read,
}


@router.websocket("/ws/chat/{room_id}")
async def websocket_chat(
    websocket: WebSocket,
    room_id: str,
    current_user: User = Depends(get_current_user_ws),
    db: AsyncSession = Depends(get_db),
) -> None:
    # --- Validate room membership ---
    try:
        room_uuid = uuid.UUID(room_id)
    except ValueError:
        await websocket.close(code=4001, reason="Invalid room ID")
        return

    room_repo = RoomRepository(db)
    if not await room_repo.is_member(room_uuid, current_user.id):
        await websocket.close(code=4003, reason="Not a member of this room")
        return

    user_id_str = str(current_user.id)

    await manager.connect(websocket, room_id, user_id_str)
    await set_online(user_id_str, current_user.username)

    # Notify room that user came online
    await manager.broadcast_to_room(room_id, {
        "type": "presence",
        "user_id": user_id_str,
        "username": current_user.username,
        "status": "online",
    })

    heartbeat_task = asyncio.create_task(_heartbeat(user_id_str, current_user.username))

    try:
        while True:
            try:
                payload = await asyncio.wait_for(websocket.receive_json(), timeout=120)
            except asyncio.TimeoutError:
                # No message in 120s — close stale connection
                break

            msg_type: str = payload.get("type", "")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            handler = _DISPATCH.get(msg_type)
            if handler is None:
                await websocket.send_json({"type": "error", "message": f"Unknown type: {msg_type}"})
                continue

            try:
                await handler(payload, current_user, room_id, db)
                await db.commit()
            except Exception as exc:
                await db.rollback()
                logger.error("ws_handler_error", type=msg_type, error=str(exc), user_id=user_id_str)
                await websocket.send_json({"type": "error", "message": "Internal error processing message"})

    except WebSocketDisconnect:
        logger.info("ws_client_disconnected", user_id=user_id_str, room_id=room_id)
    finally:
        heartbeat_task.cancel()
        await manager.disconnect(room_id, user_id_str)
        await set_offline(user_id_str, current_user.username)

        await manager.broadcast_to_room(room_id, {
            "type": "presence",
            "user_id": user_id_str,
            "username": current_user.username,
            "status": "offline",
        })

        # Update last_seen in DB (fire-and-forget; ok if this fails)
        try:
            user_repo = UserRepository(db)
            await user_repo.update_last_seen(current_user.id)
            await db.commit()
        except Exception:
            pass


async def _heartbeat(user_id: str, username: str) -> None:
    """Refresh Redis presence TTL periodically."""
    while True:
        await asyncio.sleep(_HEARTBEAT_INTERVAL)
        await refresh_presence(user_id, username)
