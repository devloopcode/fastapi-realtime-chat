"""
Redis Pub/Sub subscriber — the bridge for horizontal scaling.

Each FastAPI process runs one background task that subscribes to all room
and presence channels. When a message arrives from Redis, it is broadcast
to the local WebSocket connections in this process.

Channel naming:
  channel:room:{room_id}   — chat messages and read receipts
  channel:typing:{room_id} — typing indicators
  channel:presence         — online/offline events

This design means:
  Process A receives a chat_message → persists it → publishes to Redis.
  Process B (and A itself) receive the Redis event → broadcast to local WS connections.

The subscriber re-subscribes automatically on connection loss (reconnect loop).
"""
from __future__ import annotations

import asyncio
import json

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging import get_logger
from app.managers.connection_manager import manager

logger = get_logger(__name__)


async def _handle_message(channel: str, data: str) -> None:
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        logger.warning("redis_invalid_json", channel=channel, raw=data[:200])
        return

    msg_type = payload.get("type")

    if channel.startswith("channel:room:"):
        room_id = channel.removeprefix("channel:room:")
        await manager.broadcast_to_room(room_id, payload)

    elif channel.startswith("channel:typing:"):
        room_id = channel.removeprefix("channel:typing:")
        await manager.broadcast_to_room(room_id, payload)

    elif channel == "channel:presence":
        # Broadcast presence events to all connected users so they see who's online
        user_id = payload.get("user_id", "")
        # Send to everyone who is connected (across all rooms)
        # We iterate over all current connections; this is per-process only.
        for room_id, user_map in list(manager._rooms.items()):
            await manager.broadcast_to_room(room_id, payload)

    else:
        logger.debug("redis_unknown_channel", channel=channel)


async def run_subscriber() -> None:
    """Long-running task. Reconnects automatically on Redis failure."""
    while True:
        try:
            r = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            pubsub = r.pubsub()

            # Subscribe to presence + patterned channels
            await pubsub.subscribe("channel:presence")
            await pubsub.psubscribe("channel:room:*", "channel:typing:*")

            logger.info("redis_subscriber_started")

            async for message in pubsub.listen():
                if message["type"] not in ("message", "pmessage"):
                    continue
                channel: str = message.get("channel") or message.get("pattern", "")
                data: str = message.get("data", "")
                if data:
                    asyncio.create_task(_handle_message(channel, data))

        except asyncio.CancelledError:
            logger.info("redis_subscriber_stopped")
            raise
        except Exception as exc:
            logger.error("redis_subscriber_error", error=str(exc))
            await asyncio.sleep(2)  # backoff before reconnect
        finally:
            try:
                await r.aclose()
            except Exception:
                pass
