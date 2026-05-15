"""
Presence service — tracks online/offline state in Redis.

Key design:
  presence:{user_id} = username   (TTL = settings.presence_ttl_seconds)

A heartbeat from the WebSocket handler refreshes the TTL every ~60s.
When the connection closes, the key is deleted immediately.
"""
from __future__ import annotations

import json

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging import get_logger
from app.managers.redis_manager import get_redis

logger = get_logger(__name__)

_PRESENCE_PREFIX = "presence:"
_CHANNEL_PRESENCE = "channel:presence"


async def set_online(user_id: str, username: str) -> None:
    r = await get_redis()
    await r.setex(f"{_PRESENCE_PREFIX}{user_id}", settings.presence_ttl_seconds, username)
    await r.publish(
        _CHANNEL_PRESENCE,
        json.dumps({"type": "presence", "user_id": user_id, "username": username, "status": "online"}),
    )
    logger.debug("presence_online", user_id=user_id)


async def set_offline(user_id: str, username: str) -> None:
    r = await get_redis()
    await r.delete(f"{_PRESENCE_PREFIX}{user_id}")
    await r.publish(
        _CHANNEL_PRESENCE,
        json.dumps({"type": "presence", "user_id": user_id, "username": username, "status": "offline"}),
    )
    logger.debug("presence_offline", user_id=user_id)


async def refresh_presence(user_id: str, username: str) -> None:
    """Extend TTL — called periodically by the WebSocket heartbeat."""
    r = await get_redis()
    await r.setex(f"{_PRESENCE_PREFIX}{user_id}", settings.presence_ttl_seconds, username)


async def get_online_users() -> list[dict[str, str]]:
    r = await get_redis()
    keys = await r.keys(f"{_PRESENCE_PREFIX}*")
    if not keys:
        return []
    usernames = await r.mget(*keys)
    result = []
    for key, username in zip(keys, usernames):
        if username:
            user_id = key.removeprefix(_PRESENCE_PREFIX)
            result.append({"user_id": user_id, "username": username, "status": "online"})
    return result


async def is_online(user_id: str) -> bool:
    r = await get_redis()
    return bool(await r.exists(f"{_PRESENCE_PREFIX}{user_id}"))
