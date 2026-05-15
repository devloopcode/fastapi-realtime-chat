"""
Typing indicator service.

Keys:  typing:{room_id}:{user_id} = username   (TTL = settings.typing_ttl_seconds)
Channel: channel:typing:{room_id}

When a key expires naturally (no explicit stop), clients infer the user stopped typing.
This keeps the system self-healing without requiring a stop event.
"""
from __future__ import annotations

import json

from app.core.config import settings
from app.core.logging import get_logger
from app.managers.redis_manager import get_redis

logger = get_logger(__name__)

_TYPING_PREFIX = "typing:"
_TYPING_CHANNEL_PREFIX = "channel:typing:"


def _key(room_id: str, user_id: str) -> str:
    return f"{_TYPING_PREFIX}{room_id}:{user_id}"


def _channel(room_id: str) -> str:
    return f"{_TYPING_CHANNEL_PREFIX}{room_id}"


async def start_typing(room_id: str, user_id: str, username: str) -> None:
    r = await get_redis()
    await r.setex(_key(room_id, user_id), settings.typing_ttl_seconds, username)
    await r.publish(
        _channel(room_id),
        json.dumps({
            "type": "typing",
            "room_id": room_id,
            "user_id": user_id,
            "username": username,
            "is_typing": True,
        }),
    )


async def stop_typing(room_id: str, user_id: str, username: str) -> None:
    r = await get_redis()
    await r.delete(_key(room_id, user_id))
    await r.publish(
        _channel(room_id),
        json.dumps({
            "type": "typing",
            "room_id": room_id,
            "user_id": user_id,
            "username": username,
            "is_typing": False,
        }),
    )


async def get_typing_users(room_id: str) -> list[dict[str, str]]:
    r = await get_redis()
    keys = await r.keys(f"{_TYPING_PREFIX}{room_id}:*")
    if not keys:
        return []
    usernames = await r.mget(*keys)
    result = []
    for key, username in zip(keys, usernames):
        if username:
            uid = key.split(":")[-1]
            result.append({"user_id": uid, "username": username})
    return result
